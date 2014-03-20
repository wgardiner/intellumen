from . import app
from . import db
from . import flash_errors, FormDboLinker

import flask
from flask import request, abort, render_template, url_for, flash, redirect, session, jsonify, g

from redis import Redis
red = Redis()

import sqlalchemy
from . import errors
from decimal import Decimal
import urllib2,re,urllib,random,time,sys,json
import datetime

import logging
logging.basicConfig()
logging.getLogger().setLevel(logging.DEBUG)

class Color(object):
	def __init__(self, **kwargs):
		for k, v in kwargs.iteritems():
			setattr(self, k, v)

#### REGION: ROOT
@app.route('/', methods=["GET"])
def index():
    return render_template("slider.html", colors=[
    	Color(name="Red", slug="red", value=125, hex="ff5600"),
    	Color(name="Green", slug="green", value=11, hex="2fff00"),
    	Color(name="Blue", slug="blue", value=220, hex="0066ff"),
    	Color(name="Amber", slug="amber", value=110, hex="ffd700"),
    	Color(name="Cool White", slug="coolWhite", value=110, hex="fff9fd"),
    	Color(name="Warm White", slug="warmWhite", value=110, hex="ffc58f")
    ])



@app.route('/colorVals', methods=['POST'])
def colorVals_post():
    red.publish('colorVals', json.dumps(request.json))
    red.publish('commands', json.dumps({'command':'setcolor', 'color': request.json}))
    return "{}"

@app.route('/startBlink', methods=['POST'])
def startBlink():
    cmd = request.json.copy()
    cmd['command'] = 'startblink'

    red.publish('commands', json.dumps(cmd))
    return '{}'

@app.route('/stopBlink', methods=['POST'])
def stopBlink():
    red.publish('commands', json.dumps({'command':'stopblink'}))
    return '{}'

@app.route('/colorStream')
def color_stream():
    def event_stream():
        pubsub = red.pubsub()
        pubsub.subscribe('colorVals')
        for message in pubsub.listen():
            yield 'data: %s\n\n' % message['data']
    return flask.Response(event_stream(), mimetype="text/event-stream")

@app.route('/commandStream')
def command_stream():
    def event_stream():
        pubsub = red.pubsub()
        pubsub.subscribe('commands')
        for message in pubsub.listen():
            yield 'data: %s\n\n' % message['data']
    return flask.Response(event_stream(), mimetype="text/event-stream")
