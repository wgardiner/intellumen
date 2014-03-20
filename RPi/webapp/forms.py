import wtforms
from flask import flash

def flash_errors(form):
    for field, errors in form.errors.items():
        for error in errors:
            flash(u"Error in the %s field - %s" % (
                getattr(form, field).label.text,
                error
            ))

class FormDboLinker(object):
    def __init__(self, form, dbo):
        self._dbo = dbo
        self._form = form

    def __getattr__(self, key):
        if key in ('_dbo', '_form'):
            return super(type(self), self).__getattr__(key)
        else:
            return getattr(self._dbo, key)

    def __setattr__(self, key, value):
        if key in ('_dbo', '_form'):
            super(type(self), self).__setattr__(key, value)
        else:
            setattr(self._dbo, key, value)
            getattr(self._form, key).data = value

