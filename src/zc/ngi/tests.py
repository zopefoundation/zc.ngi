##############################################################################
#
# Copyright (c) 2004 Zope Corporation and Contributors.
# All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.1 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE.
#
##############################################################################
import doctest
import logging
import manuel.capture
import manuel.doctest
import manuel.testing
import sys
import threading
import unittest
import zc.ngi.async
import zc.ngi.generator
import zc.ngi.testing
import zc.ngi.wordcount

zc.ngi.async.start_thread() # Make sure the thread is already running

def test_async_cannot_connect():
    """Let's make sure that the connector handles connection failures correctly

    >>> import threading
    >>> lock = threading.Lock()
    >>> _ = lock.acquire()

    We define a simple handler that just notifies of failed connectioons.

    >>> class Handler:
    ...     def failed_connect(connection, reason):
    ...         print 'failed'
    ...         lock.release()

    >>> def connect(addr):
    ...     zc.ngi.async.connect(addr, Handler())
    ...     lock.acquire()

    We find an unused port (so when we connect to it, the connection
    will fail).

    >>> port = zc.ngi.testing.get_port()

    Now let's try to connect

    >>> connect(('localhost', port))
    failed

    """

def async_thread_has_name():
    """
    >>> len([t for t in threading.enumerate() if t.getName() == 'zc.ngi.async'])
    1
    """

def blocking_connector_handles_failed_connect():
    """
    >>> import zc.ngi.blocking
    >>> zc.ngi.blocking.open(('localhost', 42), zc.ngi.testing.connect)
    Traceback (most recent call last):
    ...
    ConnectionFailed: no such server

    """

def failure_to_bind_removes_listener_from_socket_map():
    """
    First, grab a port:

    >>> import socket, random

    >>> s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    >>> for i in range(1000):
    ...    port = random.randint(10000, 30000)
    ...    try: s.bind(('', port))
    ...    except socket.error: pass
    ...    else: break
    ... else: print 'woops'

    Get size of socket map:

    >>> size = len(zc.ngi.async._map)

    Now, trying to create a listener on the port should fail, and the
    map should remain the same size.

    >>> try: zc.ngi.async.listener(('', port), None)
    ... except socket.error: pass
    ... else: print 'oops'

    >>> len(zc.ngi.async._map) == size
    True

    >>> s.close()

    UDP:

    >>> s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    >>> for i in range(1000):
    ...    port = random.randint(10000, 30000)
    ...    try: s.bind(('', port))
    ...    except socket.error: pass
    ...    else: break
    ... else: print 'woops'

    Get size of socket map:

    >>> size = len(zc.ngi.async._map)

    Now, trying to create a listener on the port should fail, and the
    map should remain the same size.

    >>> try: zc.ngi.async.udp_listener(('', port), None)
    ... except socket.error: pass
    ... else: print 'oops'

    >>> len(zc.ngi.async._map) == size
    True

    >>> s.close()
    """

def async_error_in_client_when_conection_is_closed():
    """
If a connection is closed, we need to make sure write calls generate errors.

    >>> logger = logging.getLogger('zc.ngi')
    >>> log_handler = logging.StreamHandler(sys.stdout)
    >>> logger.addHandler(log_handler)
    >>> logger.setLevel(logging.WARNING)

    >>> server_event = threading.Event()
    >>> @zc.ngi.generator.handler
    ... def server(conn):
    ...     data = yield
    ...     print data
    ...     server_event.set()

    >>> listener = zc.ngi.async.listener(None, server)

    >>> class Connector:
    ...     def __init__(self):
    ...         self.event = threading.Event()
    ...     def connected(self, conn):
    ...         self.conn = conn
    ...         self.event.set()

    >>> connector = Connector()
    >>> zc.ngi.async.connect(listener.address, connector)
    >>> connector.event.wait(1)

OK, we've connected.  If we close the connection, we won't be able to write:

    >>> connector.conn.close()
    >>> connector.conn.write('xxx')

    >>> connector.conn.writelines(['xxx', 'yyy'])

Similarly if the server closes the connection:

    >>> connector = Connector()
    >>> zc.ngi.async.connect(listener.address, connector)
    >>> connector.event.wait(1)

    >>> connector.conn.write('aaa'); server_event.wait(1)
    aaa

    >>> connector.conn.write('xxx')

    >>> connector.conn.writelines(['xxx', 'yyy'])


    >>> logger.removeHandler(log_handler)
    >>> logger.setLevel(logging.NOTSET)

    """

def when_a_server_closes_a_connection_blocking_request_returns_reason():
    """

    >>> import zc.ngi.adapters, zc.ngi.async, zc.ngi.blocking
    >>> @zc.ngi.adapters.Sized.handler
    ... def echo1(c):
    ...     c.write((yield))

    >>> listener = zc.ngi.async.listener(None, echo1)
    >>> @zc.ngi.adapters.Sized.handler
    ... def client(c):
    ...     c.write('test')
    ...     print '1', (yield)
    ...     print '2', (yield)
    >>> zc.ngi.blocking.request(zc.ngi.async.connect, listener.address,
    ...                         client, 1)
    ... # doctest: +ELLIPSIS
    1...
    'end of input'
    >>> listener.close()
    """

def errors_raised_by_handler_should_be_propigated_by_blocking_request():
    """
    Errors raised by handlers should propigate to the request caller,
    rather than just getting logged as usual.

    Note that this test also exercises error handling in zc.ngi.async.

    >>> from zc.ngi import async
    >>> from zc.ngi.adapters import Sized
    >>> from zc.ngi.blocking import request

    >>> @Sized.handler
    ... def echo(c):
    ...     while 1:
    ...         data = (yield)
    ...         if data == 'stop': break
    ...         c.write(data)

    >>> listener = async.listener(None, echo)

    Handle error in setup

    >>> @Sized.handler
    ... def bad(c):
    ...     raise ValueError

    >>> try: request(async.connect, listener.address, bad, 1)
    ... except ValueError: pass
    ... else: print 'oops'

    Handle error in input

    >>> @Sized.handler
    ... def bad(c):
    ...     c.write('test')
    ...     data = (yield)
    ...     raise ValueError

    >>> try: request(async.connect, listener.address, bad, 1)
    ... except ValueError: pass
    ... else: print 'oops'

    Handle error in close

    >>> @Sized.handler
    ... def bad(c):
    ...     c.write('stop')
    ...     try:
    ...         while 1:
    ...             data = (yield)
    ...     except GeneratorExit:
    ...         raise ValueError

    >>> try: request(async.connect, listener.address, bad, 1)
    ... except ValueError: pass
    ... else: print 'oops'

    Handle error in handle_exception arising from error during iteration:

    >>> @Sized.handler
    ... def bad(c):
    ...     c.writelines(XXX for i in range(2))
    ...     data = (yield)

    >>> try: request(async.connect, listener.address, bad, 1)
    ... except NameError: pass
    ... else: print 'oops'

    >>> listener.close()
    """

def async_handling_iteration_errors():
    """

    >>> from zc.ngi import async
    >>> from zc.ngi.adapters import Sized
    >>> from zc.ngi.blocking import request

    >>> @Sized.handler
    ... def echo(c):
    ...     while 1:
    ...         data = (yield)
    ...         if data == 'stop': break
    ...         c.write(data)

    >>> listener = async.listener(None, echo)

    Handler with no handle_exception but with a handle close.

    >>> event = threading.Event()
    >>> class Bad:
    ...    def connected(self, connection):
    ...        connection.setHandler(self)
    ...        connection.writelines(XXX for i in range(2))
    ...    def handle_close(self, connection, reason):
    ...        print 'closed', reason
    ...        event.set()

    >>> zc.ngi.async.connect(listener.address, Bad()); event.wait(1)
    closed Bad instance has no attribute 'handle_exception'

    >>> listener.close()
    """

class BrokenConnect:

    connected = failed_connect = __call__ = lambda: xxxxx

class BrokenAfterConnect:

    def connected(self, connection):
        connection.write("Hee hee\0")
        connection.setHandler(self)

    __call__ = connected

    handle_input = handle_close = lambda: xxxxx

def async_evil_setup(test):

    # Uncomment the next 2 lines to check that a bunch of lambda type
    # errors are logged.
    #import logging
    #logging.getLogger().addHandler(logging.StreamHandler())

    # See if we can break the main loop before running the async test

    # Connect to bad port with bad handler

    port = zc.ngi.wordcount.get_port()
    addr = 'localhost', port
    zc.ngi.async.connect(addr, BrokenConnect())

    # Start the server and connect to a good port with a bad handler

    port = zc.ngi.wordcount.start_server_process(zc.ngi.async.listener)
    addr = 'localhost', port
    zc.ngi.async.connect(addr, BrokenAfterConnect())

    # Stop the server
    zc.ngi.wordcount.stop_server_process(zc.ngi.async.connect, addr)

    # Create a lister with a broken server and connect to it
    port = zc.ngi.wordcount.get_port()
    addr = 'localhost', port
    zc.ngi.async.listener(addr, BrokenConnect())
    zc.ngi.async.connect(addr, BrokenAfterConnect())

    # Create a lister with a broken Server handler and connect to it
    port = zc.ngi.wordcount.get_port()
    addr = 'localhost', port
    zc.ngi.async.listener(addr, BrokenAfterConnect())
    zc.ngi.async.connect(addr, BrokenAfterConnect())


def test_suite():
    return unittest.TestSuite([
        manuel.testing.TestSuite(
            manuel.capture.Manuel() + manuel.doctest.Manuel(),
            'doc/index.txt',
            ),
        doctest.DocFileSuite(
            'README.txt',
            'testing.test',
            'message.txt',
            'adapters.txt',
            'blocking.txt',
            'async-udp.test',
            ),
        doctest.DocFileSuite(
            'async.txt',
            setUp=async_evil_setup,
            ),
        doctest.DocTestSuite(),
        ])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
