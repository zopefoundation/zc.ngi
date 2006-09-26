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
