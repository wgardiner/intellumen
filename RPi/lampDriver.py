from redis import Redis
import datetime, time
import threading
import Queue
import json

scheduler_queue = Queue.PriorityQueue()

def remove_blink_commands():
    cmds = []
    while True:
        try:
            pri, lampCmd = scheduler_queue.get(False)
        except Queue.Empty:
            break
        if lampCmd['command'] != 'blink':
            cmds.append((pri, lampCmd))

    # Put all the non-blink commands back onto the queue
    for elm in cmds:
        scheduler_queue.put(elm)

def update_color_state(redis):
    pass #TODO: Write me, and probably make a lamp class

def update_sensor_state(redis):
    pass #TODO: Write me, and probably make a lamp class

def set_color(redis, color, fromUi=False):
    try:
        currentColor = json.loads(redis.get('ledColor'))
    except:
        currentColor = None
        raise

    if color != currentColor:
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

            if 'ledColor' in stch:
                scheduler_queue.put((datetime.datetime.utcnow(), {'command': 'setcolor', 'color': stch['ledColor']}))

            if 'blink' in stch:
                # remove existing blink commands
                remove_blink_commands()

                blink = stch['blink']
                if blink['blinking']:
                    # add a new blink command
                    scheduler_queue.put((datetime.datetime.utcnow(), {'command': 'blink', 'ms': blink['ms'], 'color1': blink['color1'], 'color2': blink['color2']}))

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
                set_color(red, cmd['color1'])
                # schedule other half of blink
                scheduler_queue.put((datetime.datetime.utcnow() + datetime.timedelta(0, cmd['ms'] / 1000.0), {'command': 'blink', 'ms': cmd['ms'], 'color1': cmd['color2'], 'color2': cmd['color1']}))

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
