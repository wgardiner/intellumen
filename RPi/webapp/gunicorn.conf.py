import multiprocessing

bind = "unix:/tmp/gunicorn_zincap.sock"
workers = multiprocessing.cpu_count() * 2 + 1
proc_name = "gunicorn_zincap"
#accesslog = "/tmp/gunicorn_autopricer-access.log"
#errorlog = "/tmp/gunicorn_autopricer-error.log"
#accesslog = "/var/log/autopricer/gunicorn-access.log"
#errorlog = "/var/log/autopricer/gunicorn-error.log"
pidfile = "/tmp/gunicorn_zincap.pid"
