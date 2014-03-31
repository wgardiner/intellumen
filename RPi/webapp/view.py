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
    red.publish('commands', json.dumps(cmd))
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
    def inPast(self):
        return self.at < datetime.datetime.utcnow()

    @property
    def at(self):
        return datetime.datetime.utcfromtimestamp(int(self.event['at']))

    @property
    def commandStr(self):
        return str(self.event['inner']['command'])

    @property
    def atStr(self):
        return datetime.datetime.fromtimestamp(int(self.event['at'])).strftime("%Y-%m-%d %H:%M:%S") # localtime on purpose

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
    print repr([e.__dict__ for e in events])
    return render_template("events.html", events=events)

@app.route('/events/new', methods=["GET"])
def newevent():
    return render_template("newevent.html")

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

