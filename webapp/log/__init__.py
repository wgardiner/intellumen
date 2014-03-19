import logging, logging.handlers
import datetime

class ContextFormatter(logging.Formatter):
    ''' A context-data aware subclass of the base formatter. '''
    def format(self,record):
        # monkeypatch the context onto the record
        try:
            record.context_data = self.context_data
        except AttributeError:
            record.context_data = None

        # Call the superclass
        return super(type(self),self).format(record)

def set_up_loggers():
    ''' Set up the loggers for Zinc. Some serious black magic in this file. '''
    from .smtp import SMTPHandler, EmailFormatter
    from .. import app

    if not hasattr(logging, 'DEBUGV'):
        # Add DEBUGV level
        logging.DEBUGV = 9 
        logging.addLevelName(logging.DEBUGV, "DEBUGV")
        def debugv(self, message, *args, **kws):
            # Yes, logger takes its '*args' as 'args'.
            if self.isEnabledFor(logging.DEBUGV):
                self._log(logging.DEBUGV, message, args, **kws) 
        logging.Logger.debugv = debugv

    # turn up requests and amqplib logging levels
    logging.getLogger("requests").setLevel(logging.ERROR)
    logging.getLogger("amqplib").setLevel(logging.ERROR)
    
    rlog = logging.getLogger()
    if not rlog.handlers or not hasattr(rlog, 'zincSetup'): 
        rlog.zincSetup = True
        rlog.setLevel(logging.DEBUG)

        
        if app.config['LOG_TO_EMAIL']:
            se = app.config['SMTP_SETTINGS']
            # log CRITICAL and up to email
            eh = SMTPHandler(
                se['host'],
                se['from'],
                se['critical_to'],
                subject=None,
                credentials=se['credentials'],
                secure=tuple(),
                sms=False,
                start_at=datetime.datetime.utcnow() + datetime.timedelta(0,10) # hide errors for 10 seconds
            )
            eh.setFormatter(EmailFormatter()) 
            eh.setLevel(logging.CRITICAL)
            rlog.addHandler(eh)
        
        # log DEBUG and up to the filesystem (make sure to rotate!)
        wfh = logging.handlers.WatchedFileHandler( app.config['LOG_FILE_PATH'] ) # create a watched file handler
        wfh.setFormatter( ContextFormatter('%(asctime)s:%(name)s:%(levelname)s:%(pathname)s(%(lineno)s):%(context_data)s:%(message)s') )
        wfh.setLevel(logging.DEBUG)
        rlog.addHandler(wfh)

        # Log to screen as well
        sh = logging.StreamHandler()
        sh.setFormatter( ContextFormatter('%(levelname)s:%(name)s:%(context_data)s:%(message)s') )
        rlog.addHandler(sh)

def set_logging_context(context=None):
    ''' Call this function to monkeypatch a property 'context_data' onto all the defined logging formatters. '''
    rlog = logging.getLogger()
    for handler in rlog.handlers:
        if handler.formatter is not None:
            handler.formatter.context_data = context

__all__ = ['set_up_loggers','set_logging_context']
