import logging
import datetime
import socket

class BaseSMTPHandler(logging.Handler):
    """
    A handler class which sends an SMTP email for each logging event.
    """
    def __init__(self, mailhost, fromaddr, toaddrs, subject,
                 credentials=None, secure=None, timeout=5.0):
        """
        Initialize the handler.

        Initialize the instance with the from and to addresses and subject
        line of the email. To specify a non-standard SMTP port, use the
        (host, port) tuple format for the mailhost argument. To specify
        authentication credentials, supply a (username, password) tuple
        for the credentials argument. To specify the use of a secure
        protocol (TLS), pass in a tuple for the secure argument. This will
        only be used when authentication credentials are supplied. The tuple
        will be either an empty tuple, or a single-value tuple with the name
        of a keyfile, or a 2-value tuple with the names of the keyfile and
        certificate file. (This tuple is passed to the `starttls` method).
        A timeout in seconds can be specified for the SMTP connection (the
        default is one second).
        """
        logging.Handler.__init__(self)
        if isinstance(mailhost, tuple):
            self.mailhost, self.mailport = mailhost
        else:
            self.mailhost, self.mailport = mailhost, None
        if isinstance(credentials, tuple):
            self.username, self.password = credentials
        else:
            self.username = None
        self.fromaddr = fromaddr
        if isinstance(toaddrs, str):
            toaddrs = [toaddrs]
        self.toaddrs = toaddrs
        self.subject = subject
        self.secure = secure
        self.timeout = timeout

    def getSubject(self, record):
        """
        Determine the subject for the email.

        If you want to specify a subject line which is record-dependent,
        override this method.
        """
        return self.subject

    def emit(self, record):
        """
        Emit a record.

        Format the record and send it to the specified addressees.
        """
        try:
            import smtplib
            from email.utils import formatdate
            port = self.mailport
            if not port:
                port = smtplib.SMTP_PORT
            smtp = smtplib.SMTP(self.mailhost, port, timeout=self.timeout)
            msg = self.format(record)
            msg = "From: %s\r\nTo: %s\r\nSubject: %s\r\nDate: %s\r\nContent-type: text/html\r\n\r\n%s" % (
                            self.fromaddr,
                            ",".join(self.toaddrs),
                            self.getSubject(record),
                            formatdate(), msg)
            if self.username:
                if self.secure is not None:
                    smtp.ehlo()
                    smtp.starttls(*self.secure)
                    smtp.ehlo()
                smtp.login(self.username, self.password)
            smtp.sendmail(self.fromaddr, self.toaddrs, msg)
            smtp.quit()
        except Exception as e:
            self.handleError(record)

class EmailFormatter(logging.Formatter):
    def format(self, record):
        """Format exception object as a string"""
        msg = record.msg
        if record.args:
            msg = msg % record.args
        record.message = msg
        htmlmessage = msg.replace('<','&lt;').replace('>','&gt;')

        r = """A message with severity <tt>{0.levelname}</tt> occurred on <i>{hostname}</i>:
            <br/><pre style='padding-left:5em;'>{htmlmessage}</pre>
            This message was generated at <strong>{0.pathname}({0.lineno})</strong>.<br/>""".format(record,hostname=socket.gethostname(),htmlmessage=htmlmessage)

        try:
            if self.context_data:
                r += "The following extra context information was attached: <strong>{0.context_data}</strong><br/>".format(self)
        except AttributeError: pass

        try:
            if record.exc_info:
                tb = self.formatException(record.exc_info)
                r += "This message had the following traceback attached:<br/><pre style='padding-left:5em'>{0}</pre><br/>".format(tb)
        except AttributeError: pass

        r += "More information can be found in the debug logs."
        
        return r

class SMSFormatter(logging.Formatter):
    def format(self, record):
        """Format exception object as a string"""
        msg = record.msg
        if record.args:
            msg = msg % record.args
        record.message = msg
        
        smessage = "[{0}] {1}".format(record.levelname[0],record.message)
        smessage = smessage.split('\n')[0].strip() # first line
        if len(smessage) > 139: smessage = smessage[:136] + '...' # and not more than 140 char

        return smessage
        
class SMTPHandler(BaseSMTPHandler):
    def __init__(self,*args,**kwargs):
        self.start_at = None
        self.sms = None
        self.started = None
        if 'sms' in kwargs:
            self.sms = kwargs['sms']
            del kwargs['sms']
        if 'start_at' in kwargs:
            self.start_at = kwargs['start_at']
            del kwargs['start_at']
        super(type(self),self).__init__(*args,**kwargs)

    def getSubject(self,record):
        if self.sms: return ""
        else: 
            if not record.message: 
                record.message = record.msg
                if record.args: record.message = record.msg % record.args
            smessage = record.message.split('\n')[0].strip() # first line
            if len(smessage) > 80: smessage = smessage[:77] + '...' # and not more than 80 char
            return "[{0}] '{1}' on {2}".format(record.levelname,smessage,socket.gethostname())

    def emit(self,*args,**kwargs):
        if self.started or not self.start_at or self.start_at < datetime.datetime.utcnow():
            self.started = True
            super(type(self),self).emit(*args,**kwargs)

