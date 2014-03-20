from flask import request, Response, abort
from functools import wraps
from werkzeug.datastructures import Authorization
from . import app
from . import settings

# be conservative in what you do
# and liberal in what you accept
 
# We have to include a copy of werkzeug's authorization handling code to handle
# the case where no colon is appended to the header correctly.
# The RFC is unclear about required behaviour if there is no password specified 
# and implementations differ.
@app.before_request
def _reparse_auth_header():
    """Parse an HTTP basic/digest authorization header transmitted by the web
    browser.  The return value is either `None` if the header was invalid or
    not given, otherwise an :class:`~werkzeug.datastructures.Authorization`
    object.

    :param value: the authorization header to parse.
    :return: a :class:`~werkzeug.datastructures.Authorization` object or `None`.
    """
    value = request.headers.get('authorization')

    if not value: return
    try: 
        # split no more than once on any whitespace
        auth_type, auth_info = value.split(None, 1)
        auth_type = auth_type.lower()
    except ValueError: return
    if auth_type == 'basic':
        try:
            tup = auth_info.decode('base64').split(':', 1)
            username = tup[0]
            password = tup[1] if len(tup) == 2 else ''
        except Exception as e: return
        request.authorization = Authorization('basic', {'username': username,
                                                        'password': password})

def require_auth(f):
    @wraps(f)
    def decorated(*args,**kwargs):
        un = None; pw = None

        auth = request.authorization
        if auth:
            un = auth.username
            pw = auth.password

        if un and pw:
            if not (un == settings.adminUsername and pw == settings.adminPassword):
	        return Response('Enter admin username and password', 401, {'WWW-Authenticate': 'Basic realm="Zinc"'})
        else:
            return Response('Enter admin username and password', 401, {'WWW-Authenticate': 'Basic realm="Zinc"'})

        return f(*args,**kwargs)
    return decorated

