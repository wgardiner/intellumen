from . import app
from . import flash_errors, FormDboLinker

import flask
from flask import request, abort, render_template, url_for, flash, redirect, session, jsonify, g

from redis import Redis
red = Redis()

from . import errors
from decimal import Decimal
import urllib2,re,urllib,random,time,sys,json,uuid
import datetime

import logging
logging.basicConfig()
logging.getLogger().setLevel(logging.DEBUG)

STATE_VARS = ['ledColor', 'blink', 'fade']

def get_config():
    return {
        'colors': [
            {"name": "Red", "slug": "red", "value": 0, "hex": "ff5600", "weight": 1},
            {"name": "Green", "slug": "green", "value": 0, "hex": "2fff00", "weight": 1},
            {"name": "Blue", "slug": "blue", "value": 0, "hex": "0066ff", "weight": 1},
            {"name": "Amber", "slug": "amber", "value": 0, "hex": "ffd700", "weight": 1},
            {"name": "Cool White", "slug": "coolWhite", "value": 0, "hex": "fff9fd", "weight": 0},
            {"name": "Warm White", "slug": "warmWhite", "value": 0, "hex": "ffc58f", "weight": 0}
        ]
    }

def get_state():
    state = {}
    for name in STATE_VARS:
        data = red.get(name)
        if data:
            state[name] = json.loads(data)
    return state

def handle_command(cmd):
    stateName = None
    data = None
#    emit = None

    if cmd['command'] == 'setcolor':
        stateName = 'ledColor'
        data = cmd['color']
    elif cmd['command'] == 'addevent':
        stateName = 'addevent'
        data = {'at': int(cmd['at']), 'inner': cmd['inner'], 'id': uuid.uuid4().hex}
    elif cmd['command'] == 'delevent':
        stateName = 'delevent'
        data = {'id': cmd['id']}
    elif cmd['command'] == 'startblink':
        stateName = 'blink'
        data = {'reset': True, 'blinking': True, 'color1': cmd['color1'], 'color2': cmd['color2'], 'ms': int(cmd['ms']), 'numBlinks': cmd['numBlinks']}
    elif cmd['command'] == 'stopblink':
        stateName = 'blink'
        data = {'reset': True, 'blinking': False}
    elif cmd['command'] == 'startfade':
        stateName = 'fade'
        data = {'reset': True, 'fading': True, 'color1': cmd['color1'], 'color2': cmd['color2'], 'time': int(cmd['time'])}
    elif cmd['command'] == 'stopfade':
        stateName = 'fade'
        data = {'reset': True, 'fading': False}
#    elif cmd['command'] == 'getcolor':
#        emit = {'command': 'getcolor'}

    if stateName and data:
        red.publish('stateChanges', json.dumps({stateName: data}))
        red.set(stateName, json.dumps(data))

 #   if emit:
 #       red.publish('lampCommands', json.dumps(emit))

    return {}

class DisplayEvent(object):
    def __init__(self, event):
        self.event = event

    @property
    def detailsStr(self):
        c = self.event['inner'].copy()
        del c['command']
        return repr(c)

    @property
    def commandStr(self):
        return str(self.event['inner']['command'])

    @property
    def atStr(self):
        dt = datetime.datetime.fromtimestamp(int(self.event['at']))
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    @property
    def id(self):
        return self.event['id']

#### REGION: ROOT
@app.route('/', methods=["GET"])
def index():
    return render_template("index.html")

@app.route('/events', methods=["GET"])
def events():
    levents = json.loads(red.get('events') or '[]')
    events = [DisplayEvent(e) for e in levents]
    return render_template("events.html", events=events)

@app.route('/json/config', methods=['GET'])
def config():
    return jsonify(get_config())

@app.route('/json/state', methods=['GET'])
def state():
    return jsonify(get_state())

@app.route('/json/command', methods=['POST'])
def command():
    return jsonify(handle_command(request.json))

@app.route('/json/stream')
def stream():
    def event_stream():
        pubsub = red.pubsub()
        pubsub.subscribe('stateChanges')
        for message in pubsub.listen():
            yield 'data: %s\n\n' % message['data']
    return flask.Response(event_stream(), mimetype="text/event-stream")

