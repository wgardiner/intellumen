from redis import Redis
import datetime, time
import threading
import Queue
import json
import operator
import subprocess

import logging
logging.basicConfig()
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

scheduler_queue = Queue.PriorityQueue()

COMMANDER = './commander'

def change_state(redis, key, val, publish=True):
    redis.set(key, json.dumps(val))
    if publish:
        redis.publish('stateChanges', json.dumps({key: val}))

def change_state_var(redis, state, key, val):
    s = json.loads(redis.get(state))
    s[key] = val
    redis.set(state, json.dumps(s))
    s['reset'] = False
    redis.publish('stateChanges', json.dumps({state: s}))

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

currentColor = None
def set_color(redis, color, fromUi=False):
    global currentColor

    color = color.copy()

    # round the color to the nearest interger first
    for channel in color:
        color[channel] = int(round(color[channel]))

    if color != currentColor:
        redis.publish('lampCommands', json.dumps({'command':'setcolor', 'color':color}))
        logger.debug('set lamp color to: %s', color)

        currentColor = color

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

            logger.debug('got state change: %s', stch)

            if hasattr(self, '_shutdown') and self._shutdown: return

            now = datetime.datetime.utcnow()

            if 'ledColor' in stch:
                scheduler_queue.put((now, {'command': 'setcolor', 'sch': now, 'color': stch['ledColor']}))

            if 'blink' in stch:
                blink = stch['blink']

                if blink.get('reset', None):
                    # remove existing blink commands
                    remove_commands('blink')

                    if blink['blinking']:
                        # add a new blink command
                        scheduler_queue.put((now, {'command': 'blink', 'sch': now, 'ms': blink['ms'], 'color1': blink['color1'], 'color2': blink['color2'], 'numBlinks': blink['numBlinks']}))

            if 'fade' in stch:
                fade = stch['fade']

                if fade.get('reset', None):
                    # remove existing fade commands
                    remove_commands('fade')

                    if fade['fading']:
                        # add a new fade command
                        scheduler_queue.put((now, {'command': 'fade', 'sch': now, 'stopAt': fade['color2'], 'currentAt': fade['color1'], 'startAt': fade['color1'], 'time': fade['time']}))

class RedisLampCommandThread(threading.Thread):
    def getProcess(self):
        if not hasattr(self, 'subproc') or self.subproc.poll() is not None:
            logger.debug("spawning subprocess")
            self.subproc = subprocess.Popen([COMMANDER], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        return self.subproc

    def sendMessage(self, packet):
        ''' send packet using the commander process (spawn only 1 of these). return the response packet. '''
        p = self.getProcess()
        try:
            p.stdin.write(' '.join([str(int(s)) for s in packet]) + '\n')
            #resp = p.stdout.readline().strip()
            #if resp:
            #    resp = [int(r) for r in resp.split(' ')]
            #    return resp
            #else: return None
        except: raise

    def run(self):
        red = Redis()
        pubsub = red.pubsub()
        pubsub.subscribe('lampCommands')

        for message in pubsub.listen():
            try:
                cmd = json.loads(message['data'])
            except TypeError:
                logger.debug("DERP")
                time.sleep(1)
                continue

            logger.debug('Got lamp command: %s', cmd)

            # send the command
            if cmd['command'] == 'setcolor':
                c = cmd['color']
                packet = [1, c['red'], c['green'], c['blue'], c['amber'], c['coolWhite'], c['warmWhite']]
                t = time.time()
                self.sendMessage(packet)
                logger.debug('took %.2f ms to send command', (time.time() - t) * 1000)

            # assume it succeeded
            ###scheduler_queue.put((datetime.datetime.utcnow(), cmd))


class LampThread(threading.Thread):
    def run(self):
        red = Redis()
        change_state(red, 'blink', {})
        change_state(red, 'fade', {})
        while True:
            time.sleep(0.010)

            if hasattr(self, '_shutdown') and self._shutdown: return

            try:
                pri, cmd = scheduler_queue.get(False, 2)
            except Queue.Empty:
                continue

            if pri > datetime.datetime.utcnow(): # it is not yet time
                #print 'pri too low', pri, datetime.datetime.utcnow(), cmd
                scheduler_queue.put((pri, cmd)) # put it back on the queue
                time.sleep(2/1000.0) # sleep for 2ms
                continue

            logger.debug("delta from sked: %.2f ms", (datetime.datetime.utcnow() - pri).total_seconds() * 1000)

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

                    if numBlinks:
                        change_state_var(red, 'blink', 'blinksRemaining', numBlinks)
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
                maxDeltaC = abs(max(deltaC.iteritems(), key=lambda x: abs(x[1]))[1])

                percentComplete = None
                for channel in fstop:
                    try:
                        percentComplete = abs(100.0 * (fstart[channel] - fcurrent[channel]) / (fstop[channel] - fstart[channel]))
                    except ZeroDivisionError:
                        pass

                if maxDeltaC != 0:
                    scaleFactor = 1.0 / maxDeltaC

                    # Hard-cap min(deltaT) at 50ms
                    if deltaT * scaleFactor < 0.050:
                        logger.debug("HARD LIMITING fade rate!")
                        scaleFactor *= 0.050 / (deltaT * scaleFactor)

                    # Apply scaling
                    deltaT *= scaleFactor
                    for channel in deltaC:
                        deltaC[channel] *= scaleFactor

                    logger.debug("Rescheduling fade change in %.2f ms", deltaT * 1000)

                    # Find the new color
                    for channel in fcurrent:
                        fcurrent[channel] += deltaC[channel]

                    ### KLUDGE.... if we're blinking, don't change color in the fade

                    blinkState = json.loads(red.get('blink'))
                    if not blinkState or not blinkState.get('blinking', None):
                        # Set the color
                        set_color(red, fcurrent)

                    ### END KLUDGE

                    # See if we should stop
                    nowstop = True
                    for channel in fcurrent:
                        nowstop &= (abs(fcurrent[channel] - fstop[channel]) < 1.0)

                    # schedule next event
                    if not nowstop:
                        change_state_var(red, 'fade', 'percentComplete', percentComplete)

                        scheduler_queue.put((
                            datetime.datetime.utcnow() + datetime.timedelta(0, deltaT),
                            {'command': 'fade', 'stopAt': fstop, 'currentAt': fcurrent, 'startAt': fstart, 'time': ftime, 'sch': cmd['sch']}
                        ))

                    else:
                        # Just to ensure that the final color is perfect
                        blinkState = json.loads(red.get('blink'))
                        if not blinkState or not blinkState.get('blinking', None):
                            set_color(red, fstop)

                        #change_state_var(red, 'fade', 'percentComplete', 100)

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
