"""Run the code used in the async.txt doc test to ease debugging
"""

import sys, logging
sys.path.insert(0, 'src')
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter(
    "%(name)s %(lineno)s %(levelname)s: %(message)s"))
logging.getLogger().addHandler(handler)
logging.getLogger().setLevel(logging.WARNING)

## The wordcount module has a simple word-count server and client
## implementation.  We'll run these using the async implementation.

## Let's start the wordcount server:

import zc.ngi.wordcount
import zc.ngi.async
import zc.ngi.testing
port = zc.ngi.wordcount.start_server_process(zc.ngi.async.listener)

## We passed the module and name of the listener to be used.

## Now, we'll start a number of threads that connect to the server and
## check word counts of some sample documents.  If all goes well, we
## shouldn't get any output.

import threading
addr = 'localhost', port
threads = [threading.Thread(target=zc.ngi.wordcount.client_thread,
                             args=(zc.ngi.async.connector, addr))
            for i in range(200)]

_ = [thread.start() for thread in threads]
_ = [thread.join() for thread in threads]

zc.ngi.wordcount.stop_server_process(zc.ngi.async.connector, addr)

## Let's make sure that the connector handles connection failures correctly

import threading
lock = threading.Lock()
_ = lock.acquire()

##     We define a simple handler that just notifies of failed connectioons.

class Handler:
    def failed_connect(connection, reason):
        print 'failed', reason
        lock.release()

def connect(addr):
    zc.ngi.async.connector(addr, Handler())
    lock.acquire()

##     We find an unused port (so when we connect to it, the connection
##     will fail).

port = zc.ngi.testing.get_port()

##     Now let's try to connect

connect(('localhost', port))
##     failed connection failed
