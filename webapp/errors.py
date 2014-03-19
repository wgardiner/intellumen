import flask
from . import app

@app.errorhandler(400)
def _handle_errors(err):
    return flask.render_template('errors/400.html', adminEmail=settings.adminEmail), 400

