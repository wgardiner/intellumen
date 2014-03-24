from redis import Redis
import datetime, time
import threading
import Queue
import json
import operator

scheduler_queue = Queue.PriorityQueue()

def remove_commands(command):
    cmds = []
    while True:
        try:
            pri, lampCmd = scheduler_queue.get(False)
        except Queue.Empty:
            break
        if lampCmd['command'] != command:
            cmds.append((pri, lampCmd))

    # Put all the non-blink commands back onto the queue
    for elm in cmds:
        scheduler_queue.put(elm)

def update_color_state(redis):
    pass #TODO: Write me, and probably make a lamp class

def update_sensor_state(redis):
    pass #TODO: Write me, and probably make a lamp class

def set_color(redis, color, fromUi=False):
    color = color.copy()

    # round the color to the nearest interger first
    for channel in color:
        color[channel] = int(round(color[channel]))
    
    # Load the current color
    try:
        currentColor = json.loads(redis.get('ledColor'))
    except:
        currentColor = None
        raise

    if color != currentColor:
        # TODO: Set the color
        print 'would set lamp color to:', color

        if not fromUi:
            redis.publish('stateChanges', json.dumps({'ledColor': color}))
        redis.set('ledColor', json.dumps(color))

class RedisStateMonitorThread(threading.Thread):
    def run(self):
        red = Redis()
        pubsub = red.pubsub()
        pubsub.subscribe('stateChanges')
        for message in pubsub.listen():
            try:
                stch = json.loads(message['data'])
            except TypeError:
                time.sleep(1)
                continue

            print 'got state change', stch

            if hasattr(self, '_shutdown') and self._shutdown: return

            now = datetime.datetime.utcnow()

            if 'ledColor' in stch:
                scheduler_queue.put((now, {'command': 'setcolor', 'sch': now, 'color': stch['ledColor']}))

            if 'blink' in stch:
                # remove existing blink commands
                remove_commands('blink')

                blink = stch['blink']
                if blink['blinking']:
                    # add a new blink command
                    scheduler_queue.put((now, {'command': 'blink', 'sch': now, 'ms': blink['ms'], 'color1': blink['color1'], 'color2': blink['color2'], 'numBlinks': blink['numBlinks']}))

            if 'fade' in stch:
                # remove existing fade commands
                remove_commands('fade')

                fade = stch['fade']
                if fade['fading']:
                    # add a new fade command
                    scheduler_queue.put((now, {'command': 'fade', 'sch': now, 'stopAt': fade['color2'], 'currentAt': fade['color1'], 'startAt': fade['color1'], 'time': fade['time']}))

class RedisLampCommandThread(threading.Thread):
    def run(self):
        red = Redis()
        pubsub = red.pubsub()
        pubsub.subscribe('lampCommands')
        for message in pubsub.listen():
            try:
                cmd = json.loads(message['data'])
            except TypeError:
                time.sleep(1)
                continue

            print 'got command', cmd

            scheduler_queue.put((datetime.datetime.utcnow(), cmd))


class LampThread(threading.Thread):
    def run(self):
        red = Redis()
        while True:
            if hasattr(self, '_shutdown') and self._shutdown: return

            try:
                pri, cmd = scheduler_queue.get(False, 2)
            except Queue.Empty:
                continue 

            if pri > datetime.datetime.utcnow(): # it is not yet time
                #print 'pri too low', pri, datetime.datetime.utcnow(), cmd
                scheduler_queue.put((pri, cmd)) # put it back on the queue
                time.sleep(10/1000.0) # sleep for 10ms
                continue

            if cmd['command'] == 'setcolor':
                set_color(red, cmd['color'], fromUi=True)

            elif cmd['command'] == 'refreshcolor':
                update_color_state(red)

            elif cmd['command'] == 'readsensor':
                update_sensor_state(red)

            elif cmd['command'] == 'blink':
                numBlinks = cmd['numBlinks']

                set_color(red, cmd['color1'])

                if numBlinks is not None:
                    numBlinks -= 1

                if numBlinks is None or numBlinks > 0:
                    # schedule other half of blink
                    scheduler_queue.put((
                        datetime.datetime.utcnow() + datetime.timedelta(0, cmd['ms'] / 1000.0),
                        {'command': 'blink', 'ms': cmd['ms'], 'color1': cmd['color2'], 'color2': cmd['color1'], 'numBlinks': numBlinks, 'sch': cmd['sch']}
                    ))
                else:
                    red.publish('stateChanges', json.dumps({'blink': {'blinking': False}}))
                    red.set('blink', json.dumps({'blinking': False}))

            elif cmd['command'] == 'fade':
                fstop = cmd['stopAt'].copy()
                fstart = cmd['startAt'].copy()
                fcurrent = cmd['currentAt'].copy()
                ftime = cmd['time']

                # calculate deltaC (color change per second per channel (dict))
                deltaC = {}
                deltaT = 1.0
                for channel in fstop:
                    deltaC[channel] = float(fstop[channel] - fstart[channel]) / ftime

                # determine scale factor for deltaC and deltaT so the biggest change in deltaC is ~= 1 unit
                maxDeltaC = max(deltaC.iteritems(), key=lambda x: abs(x[1]))[1]

                if maxDeltaC != 0:
                    scaleFactor = 1.0 / maxDeltaC
                    
                    # Hard-cap min(deltaT) at 50ms
                    if deltaT * scaleFactor < 0.050:
                        scaleFactor *= 0.050 / (deltaT * scaleFactor)

                    # Apply scaling
                    deltaT *= scaleFactor
                    for channel in deltaC:
                        deltaC[channel] *= scaleFactor

                    # Find the new color
                    for channel in fcurrent:
                        fcurrent[channel] += deltaC[channel]

                    # Set the color
                    set_color(red, fcurrent)

                    # See if we should stop
                    nowstop = True
                    for channel in fcurrent:
                        nowstop &= (abs(fcurrent[channel] - fstop[channel]) < 1.0)

                    # schedule next event
                    if not nowstop:
                        scheduler_queue.put((
                            datetime.datetime.utcnow() + datetime.timedelta(0, deltaT), 
                            {'command': 'fade', 'stopAt': fstop, 'currentAt': fcurrent, 'startAt': fstart, 'time': ftime, 'sch': cmd['sch']}
                        ))

                    else:
                        # Just to ensure that the final color is perfect
                        set_color(red, fstop)

                        red.publish('stateChanges', json.dumps({'fade': {'fading': False}}))
                        red.set('fade', json.dumps({'fading': False}))

                else:
                    # Stop fading, zero deltaC
                    red.publish('stateChanges', json.dumps({'fade': {'fading': False}}))
                    red.set('fade', json.dumps({'fading': False}))

                
threads = [LampThread(), RedisStateMonitorThread(), RedisLampCommandThread()]

for t in threads:
    t.start()

try:
    for t in threads:
        while t.is_alive():
            t.join(1)
except:
    for t in threads:
        t._shutdown = True
    raise
