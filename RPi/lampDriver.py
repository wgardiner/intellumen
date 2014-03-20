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
            cmd = scheduler_queue.get(False)
        except Queue.Empty:
            break
        if cmd[1]['command'] != 'blink':
            cmds.append(cmd)

    for cmd in cmds:
        scheduler_queue.put(cmd)

currentColor = None
def set_color(redis, color):
    global currentColor
    if color != currentColor:
        print 'would set lamp color to:', color
        redis.publish('colorVals', json.dumps(color))

class RedisThread(threading.Thread):
    def run(self):
        red = Redis()
        pubsub = red.pubsub()
        pubsub.subscribe('commands')
        for message in pubsub.listen():
            try:
                cmd = json.loads(message['data'])
            except TypeError:
                time.sleep(1)
                continue

            print 'got command', cmd

            if hasattr(self, '_shutdown') and self._shutdown: return

            if cmd['command'] == 'startblink':
                # remove existing blink commands
                remove_blink_commands()

                # add a new blink command
                scheduler_queue.put((datetime.datetime.utcnow(), {'command': 'blink', 'ms': cmd['ms'], 'color1': cmd['color1'], 'color2': cmd['color2']}))
            
            elif cmd['command'] == 'stopblink':
                # remove existing blink commands
                remove_blink_commands()

            elif cmd['command'] == 'setcolor':
                scheduler_queue.put((datetime.datetime.utcnow(), {'command': 'setcolor', 'color': cmd['color']}))
        
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
                set_color(red, cmd['color'])

            elif cmd['command'] == 'blink':
                set_color(red, cmd['color1'])
                # schedule other half of blink
                scheduler_queue.put((datetime.datetime.utcnow() + datetime.timedelta(0, cmd['ms'] / 1000.0), {'command': 'blink', 'ms': cmd['ms'], 'color1': cmd['color2'], 'color2': cmd['color1']}))

lt = LampThread()
rt = RedisThread()
lt.start()
rt.start()
lt.join()
rt.join()
