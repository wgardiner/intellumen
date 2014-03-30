from redis import Redis
import datetime, time
import threading
import Queue
import json
import operator
import subprocess

g_t = None
def start():
    global g_t
    g_t = time.time()

def lap(a):
    print a, (time.time() - g_t) * 1000.0, 'ms'


import logging
#logging.basicConfig()
logger = logging.getLogger()
#logger.setLevel(logging.DEBUG)

scheduler_queue = Queue.PriorityQueue()
redis_queue = Queue.Queue()
lamp_queue = Queue.Queue()

COMMANDER = './commander'

MAX_RATE = 80

def change_state(key, val, publish=True):
    redis_queue.put(('set', key, val))
    if publish:
        redis_queue.put(('publish', 'stateChanges', {key: val}))

def change_state_var(state, key, val):
    redis_queue.put(('change_state_var', state, key, val))

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

g_isBlinking = None

g_currentColor = None
def set_color(color, fromUi=False):
    global g_currentColor

    color = color.copy()

    # round the color to the nearest interger first, and ensure it's in [0,255] inclusive
    for channel in color:
        color[channel] = max(min(int(round(color[channel])), 255), 0)

    if color != g_currentColor:
        lamp_queue.put({'command':'setcolor', 'color':color})
        logger.debug('set lamp color to: %s', color)

        g_currentColor = color.copy()

        color['_reset'] = False
        change_state('ledColor', color, publish=not fromUi)

class RedisStateMonitorThread(threading.Thread):
    def run(self):
        red = Redis()
        pubsub = red.pubsub()
        pubsub.subscribe('stateChanges')
        for message in pubsub.listen():
            try:
                stch = json.loads(message['data'])
            except TypeError:
                time.sleep(0)
                continue

            logger.debug('got state change: %s', stch)

            if hasattr(self, '_shutdown') and self._shutdown: return

            now = datetime.datetime.utcnow()

            if 'ledColor' in stch:
                if stch['ledColor'].get('_reset', True):
                    scheduler_queue.put((now, {'command': 'setcolor', 'sch': now, 'color': stch['ledColor']}))

            if 'blink' in stch:
                blink = stch['blink']

                global g_isBlinking
                g_isBlinking = blink and blink.get('blinking', False)

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

class LampCommandThread(threading.Thread):
    def getProcess(self):
        if not hasattr(self, 'subproc') or self.subproc.poll() is not None:
            logger.debug("spawning subprocess")
            self.subproc = subprocess.Popen([COMMANDER], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
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
        while True:
            cmd = lamp_queue.get()

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

class RedisTalkThread(threading.Thread):
    def run(self):
        redis = Redis()
        while True:
            op = redis_queue.get()
            # Example  format: ('publish', 'stream', object)
            #                  ('set', 'key', object)

            if op[0] == 'publish':
                _, key, obj = op
                redis.publish(key, json.dumps(obj))
            elif op[0] == 'set':
                _, key, obj = op
                redis.set(key, json.dumps(obj))
            elif op[0] == 'change_state_var':
                _, state, key, obj = op
                s = json.loads(redis.get(state))
                s[key] = obj
                redis.set(state, json.dumps(s))
                s['reset'] = False
                redis.publish('stateChanges', json.dumps({state: s}))

class SchedulerThread(threading.Thread):
    def run(self):
        change_state('blink', {})
        change_state('fade', {})
        while True:
            if hasattr(self, '_shutdown') and self._shutdown: return

            pri, cmd = scheduler_queue.get()
            #try:
            #    pri, cmd = scheduler_queue.get(False, 2)
            #except Queue.Empty:
            #    time.sleep(0)
            #    continue

            if pri > datetime.datetime.utcnow(): # it is not yet time
                #print 'pri too low', pri, datetime.datetime.utcnow(), cmd
                scheduler_queue.put((pri, cmd)) # put it back on the queue
                time.sleep(2/1000.0) # sleep for 2ms
                continue

            logger.debug("delta from sked: %.2f ms (%s)", (datetime.datetime.utcnow() - pri).total_seconds() * 1000, cmd['command'])

            if cmd['command'] == 'setcolor':
                set_color(cmd['color'], fromUi=True)

            #elif cmd['command'] == 'refreshcolor':
            #    update_color_state(red)

            #elif cmd['command'] == 'readsensor':
            #    update_sensor_state(red)

            elif cmd['command'] == 'blink':
                numBlinks = cmd['numBlinks']

                set_color(cmd['color1'])

                if numBlinks is not None:
                    numBlinks -= 1

                if numBlinks is None or numBlinks > 0:
                    # schedule other half of blink
                    scheduler_queue.put((
                        pri + datetime.timedelta(0, cmd['ms'] / 1000.0),
                        {'command': 'blink', 'ms': cmd['ms'], 'color1': cmd['color2'], 'color2': cmd['color1'], 'numBlinks': numBlinks, 'sch': cmd['sch']}
                    ))

                    if numBlinks:
                        change_state_var('blink', 'blinksRemaining', numBlinks)
                else:
                    change_state('blink', {'blinking': False})

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
                        continue
                    break

                if maxDeltaC != 0:
                    scaleFactor = 1.0 / maxDeltaC

                    # Hard-cap min(deltaT) at MAX_RATE ms
                    if deltaT * scaleFactor < MAX_RATE / 1000.0:
                        logger.debug("HARD LIMITING fade rate!")
                        scaleFactor *= (MAX_RATE / 1000.0) / (deltaT * scaleFactor)

                    # Apply scaling
                    deltaT *= scaleFactor
                    for channel in deltaC:
                        deltaC[channel] *= scaleFactor
                    logger.debug("Fade DC: %s", deltaC)

                    logger.debug("Rescheduling fade change in %.2f ms", deltaT * 1000)

                    # Find the new color
                    for channel in fcurrent:
                        fcurrent[channel] += deltaC[channel]

                    # See if we should stop
                    nowstop = True
                    for channel in fcurrent:
                        direction = (fstop[channel] - fstart[channel] > 0) and 1 or -1
                        nowstop &= ((fstop[channel] - fcurrent[channel]) * direction) < 1.0

                    # schedule next event
                    if not nowstop:
                        scheduler_queue.put((
                            pri + datetime.timedelta(0, deltaT),
                            {'command': 'fade', 'stopAt': fstop, 'currentAt': fcurrent, 'startAt': fstart, 'time': ftime, 'sch': cmd['sch']}
                        ))

                        change_state_var('fade', 'percentComplete', percentComplete)

                        ### KLUDGE.... if we're blinking, don't change color in the fade

                        #blinkState = json.loads(red.get('blink'))
                        #if not blinkState or not blinkState.get('blinking', None):
                        if not g_isBlinking:
                            # Set the color
                            set_color(fcurrent)

                        ### END KLUDGE

                    else:
                        # Just to ensure that the final color is perfect
                        #blinkState = json.loads(red.get('blink'))
                        #if not blinkState or not blinkState.get('blinking', None):
                        if not g_isBlinking:
                            set_color(fstop)

                        #change_state_var(red, 'fade', 'percentComplete', 100)
                        change_state('fade', {'fading': False})

                else:
                    # Stop fading, zero deltaC
                    change_state('fade', {'fading': False})


import yappi

yappi.start()
threads = [SchedulerThread(), RedisStateMonitorThread(), LampCommandThread(), RedisTalkThread()]

for t in threads:
    t.start()

try:
    for t in threads:
        while t.is_alive():
            t.join(1)
except:
    yappi.get_func_stats().print_all()
    for t in threads:
        t._shutdown = True
    raise
