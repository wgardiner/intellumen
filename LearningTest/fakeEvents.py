#!/usr/bin/python2
from learning import Event
import datetime, random, json

events = []
def addFakeEvents(prototype, dow, hour, minute, fuzziness=None):
    ''' Create a bunch of fake events like `prototype` on the given
        day of the week and hour:minute. If fuzziness is set, 
        add random.normalvariate(0, `fuzziness`) minutes. '''
    dt = datetime.datetime(2014, 1, 1, 0, 0, 0)
    while dt < datetime.datetime.utcnow():
        if dt.weekday() == dow:
            ndt = datetime.datetime(dt.year, dt.month, dt.day, hour, minute, 0)
            if fuzziness:
                ndt += datetime.timedelta(0, random.normalvariate(0, fuzziness) * 60)
            e = Event(typ = prototype.typ, val = prototype.val, dt = ndt)
            events.append(e)
        dt += datetime.timedelta(1)

# first, in the morning on the weekends, you'll add a slow fade (up at 9:30am, ready for lights out at 12am)
addFakeEvents(Event(dt=None, typ='dayfade', val={'time': 3600*14.5}), 5, 9, 30, 20)
addFakeEvents(Event(dt=None, typ='dayfade', val={'time': 3600*14.5}), 6, 9, 30, 20)

# when you get home in the evening of weekdays, you'll turn the lamp on
# and set a fast fade (ready for lights out at 11pm)
for day in range(0, 5):
    addFakeEvents(Event(dt=None, typ='set', val={'intensity': 70}), day, 17, 30, 10)
    addFakeEvents(Event(dt=None, typ='dayfade', val={'time': 3600*5.5}), day, 17, 30, 10)

# on wednesday, you come home at lunch and draw for an hour
addFakeEvents(Event(dt=None, typ='set', val={'intensity': 90}), 2, 12, 20, 5)
addFakeEvents(Event(dt=None, typ='set', val={'intensity': 0}), 2, 13, 30, 5)

print 'events = ', events
