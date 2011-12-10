##############################################################################
#
# Copyright (c) 2004 Zope Foundation and Contributors.
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
from __future__ import with_statement
from zope.testing import setupstack

import doctest
import logging
import manuel.capture
import manuel.doctest
import manuel.testing
import os
import socket
import sys
import threading
import time
import unittest
import warnings
import zc.ngi.adapters
import zc.ngi.async
import zc.ngi.generator
import zc.ngi.testing
import zc.ngi.wordcount

def blocking_warns():
    """
    >>> assert_(len(blocking_warnings) == 1)
    >>> assert_(blocking_warnings[-1].category is DeprecationWarning)
    >>> print blocking_warnings[-1].message
    The blocking module is deprecated.
    """

if sys.version_info >= (2, 6):
    # silence blocking deprecation warning
    with warnings.catch_warnings(record=True) as blocking_warnings:
        warnings.simplefilter('default')
        # omg, without record=True, warnings aren't actually caught.
        # Who thinks up this stuff?
        import zc.ngi.blocking
else:
    del blocking_warns

def wait_until(func, timeout=30):
    deadline = time.time()+timeout
    while 1:
        if func():
            break
        if time.time() > deadline:
            raise ValueError("Timeout")
        time.sleep(.01)


def test_async_cannot_connect():
    """Let's make sure that the connector handles connection failures correctly

    >>> lock = threading.Lock()
    >>> _ = lock.acquire()

    We define a simple handler that just notifies of failed connections.

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

def async_thread_management():
    """

    There's no thread by default:

    >>> len([t for t in threading.enumerate() if t.getName() == 'zc.ngi.async'])
    0

    There's a default name:

    >>> listener = zc.ngi.async.listener(None, lambda _: None)
    >>> len([t for t in threading.enumerate() if t.getName() == 'zc.ngi.async'])
    1
    >>> listener.close()
    >>> zc.ngi.async.wait(1)

    When there's nothing to do, the thread goes away:

    >>> len([t for t in threading.enumerate() if t.getName() == 'zc.ngi.async'])
    0

    If we create out own implementation, we can give it a name:

    >>> impl = zc.ngi.async.Implementation(name='bob')
    >>> listener = impl.listener(None, lambda _: None)
    >>> len([t for t in threading.enumerate() if t.getName() == 'bob'])
    1
    >>> listener.close()
    >>> impl.wait(1)

    Otherwise, it gets a slightly more descriptive name:

    >>> impl = zc.ngi.async.Implementation('')
    >>> listener = impl.listener(None, lambda _: None)
    >>> len([t for t in threading.enumerate()
    ...     if t.getName() == 'zc.ngi.async application created'])
    1
    >>> listener.close()
    >>> impl.wait(1)

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

    Make sure thread is running by creating a listener

    >>> place_holder = zc.ngi.async.listener(None, lambda _: None)
    >>> time.sleep(.1)

    Get size of socket map:

    >>> len(zc.ngi.async._map)
    2

    Now, trying to create a listener on the port should fail, and the
    map should remain the same size.

    >>> try: zc.ngi.async.listener(('', port), None)
    ... except socket.error: pass
    ... else: print 'oops'

    >>> len(zc.ngi.async._map)
    2

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

    >>> len(zc.ngi.async._map)
    2

    Now, trying to create a listener on the port should fail, and the
    map should remain the same size.

    >>> try: zc.ngi.async.udp_listener(('', port), None)
    ... except socket.error: pass
    ... else: print 'oops'

    >>> len(zc.ngi.async._map)
    2

    >>> s.close()
    >>> place_holder.close()
    """

def async_error_in_client_when_conection_is_closed():
    """
If a connection is closed, we need to make sure write calls generate errors.

    >>> @zc.ngi.generator.handler
    ... def server(conn):
    ...     while 1:
    ...        print (yield)

    >>> listener = zc.ngi.async.listener(None, server)

    >>> class Connector:
    ...     def __init__(self):
    ...         self.event = threading.Event()
    ...     def connected(self, conn):
    ...         self.conn = conn
    ...         conn.set_handler(self)
    ...         self.event.set()

    >>> connector = Connector()
    >>> zc.ngi.async.connect(listener.address, connector)
    >>> _ = connector.event.wait(1)

OK, we've connected.  If we close the connection, we won't be able to write:

    >>> connector.conn.close()

    >>> wait_until(lambda : not connector.conn)

    >>> connector.conn.write('xxx')
    Traceback (most recent call last):
    ...
    ValueError: write called on closed connection

    >>> connector.conn.writelines(['xxx', 'yyy'])
    Traceback (most recent call last):
    ...
    ValueError: writelines called on closed connection

    >>> listener.close()
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
    ...        connection.set_handler(self)
    ...        connection.writelines(XXX for i in range(2))
    ...    def handle_close(self, connection, reason):
    ...        print 'closed', reason
    ...        event.set()

    >>> zc.ngi.async.connect(listener.address, Bad()); _ = event.wait(1)
    closed Bad instance has no attribute 'handle_exception'

    >>> listener.close()
    """

def assert_(cond, *args):
    if not cond:
        raise AssertionError(*args)

def setHandler_compatibility():
    """
Make sure setHandler still works, with deprecation warnings:

The testing connection warns:

    >>> class Handler:
    ...     def handle_input(self, connection, data):
    ...         print 'got', `data`

    >>> conn = zc.ngi.testing.Connection()
    >>> with warnings.catch_warnings(record=True) as caught:
    ...     warnings.simplefilter('default')
    ...     conn.setHandler(Handler())
    ...     assert_(len(caught) == 1, len(caught))
    ...     assert_(caught[-1].category is DeprecationWarning)
    ...     print caught[-1].message
    setHandler is deprecated. Use set_handler,

    >>> conn.test_input('test')
    got 'test'

The async connections warn:

    >>> server_event = threading.Event()
    >>> class server:
    ...     def __init__(self, c):
    ...         global server_caught
    ...         with warnings.catch_warnings(record=True) as caught:
    ...             warnings.simplefilter('default')
    ...             c.setHandler(self)
    ...             server_caught = caught
    ...         server_event.set()
    ...         c.close()

    >>> client_event = threading.Event()
    >>> class client:
    ...
    ...     def connected(self, c):
    ...         global client_caught
    ...         with warnings.catch_warnings(record=True) as caught:
    ...             warnings.simplefilter('default')
    ...             c.setHandler(self)
    ...             client_caught = caught
    ...         client_event.set()
    ...         c.close()

    >>> listener = zc.ngi.async.listener(None, server)
    >>> zc.ngi.async.connect(listener.address, client())
    >>> _ = server_event.wait(1)
    >>> _ = client_event.wait(1)
    >>> listener.close()

    >>> assert_(len(server_caught) == 1)
    >>> assert_(server_caught[0].category is DeprecationWarning)
    >>> print server_caught[0].message
    setHandler is deprecated. Use set_handler,

    >>> assert_(len(client_caught) == 1)
    >>> assert_(client_caught[0].category is DeprecationWarning)
    >>> print client_caught[0].message
    setHandler is deprecated. Use set_handler,

    >>> zc.ngi.async.wait(1)

The adapters warn:

    >>> import zc.ngi.adapters
    >>> with warnings.catch_warnings(record=True) as caught:
    ...     warnings.simplefilter('default')
    ...     conn = zc.ngi.adapters.Lines(zc.ngi.testing.Connection())
    ...     conn.setHandler(Handler())
    ...     assert_(len(caught) == 1)
    ...     assert_(caught[-1].category is DeprecationWarning)
    ...     print caught[-1].message
    setHandler is deprecated. Use set_handler,

    >>> class OldConn:
    ...     def setHandler(self, h):
    ...         print 'setHandler called'
    ...         global old_handler
    ...         old_handler = h

    >>> with warnings.catch_warnings(record=True) as caught:
    ...     warnings.simplefilter('default')
    ...     conn = zc.ngi.adapters.Lines(OldConn())
    ...     handler = Handler()
    ...     conn.set_handler(handler)
    ...     assert_(len(caught) == 1)
    ...     assert_(caught[-1].category is DeprecationWarning)
    ...     print caught[-1].message
    ...     assert_(old_handler is conn)
    setHandler called
    setHandler is deprecated. Use set_handler,


    """

def EXPERIMENTAL_thready_async_servers():
    r"""
    When creating a listener with a zc.ngi.async.Implementation, you can
    pass a thready keyword options to cause each client to get it's own thread.

    >>> import functools

    >>> @functools.partial(zc.ngi.async.listener, None, thready=True)
    ... @zc.ngi.generator.handler
    ... def listener(conn):
    ...     if 'client' not in threading.currentThread().getName():
    ...         print 'oops'
    ...     yield
    >>> addr = listener.address

    So, now we're listening on listener.address, let's connect to it.

    >>> event = threading.Event()
    >>> class Connect:
    ...     def __init__(self, name):
    ...         self.name = name
    ...         event.clear()
    ...         zc.ngi.async.connect(addr, self)
    ...         event.wait(1)
    ...     def connected(self, connection):
    ...         globals()[self.name] = connection
    ...         zc.ngi.testing.PrintingHandler(connection)
    ...         event.set()

    Initially, we have no client handling threads:

    >>> def count_client_threads():
    ...     return len([t for t in threading.enumerate()
    ...                 if ("%r client" % (addr, )) in t.getName()])
    >>> count_client_threads()
    0

    >>> _ = Connect('c1')
    >>> _ = Connect('c2')

    So now we have 2 connections and we have 2 corresponding threads:

    >>> count_client_threads()
    2

    If we close the connections and wait a bit, the threads will be cleaned up:

    >>> c1.close()
    >>> c2.close()
    >>> time.sleep(.1)

    >>> count_client_threads()
    0

    Let's create another connection

    >>> _ = Connect('c1')
    >>> count_client_threads()
    1

    Now, we'll close the listener and the connection threads will be cleaned up.

    >>> listener.close()
    >>> time.sleep(.5)
    -> CLOSE end of input

    >>> count_client_threads()
    0

    >>> zc.ngi.async.wait(1)

    """

def connect_to_a_testing_listener_shoulnt_use_printing_handler():
    r"""
If we use zc.ngi.testing.connect to connect to a registered listener,
the printing handler shoudn't be used.

    >>> import zc.ngi.testing, zc.ngi.adapters
    >>> @zc.ngi.adapters.Lines.handler
    ... def echo(connection):
    ...     while 1:
    ...         connection.write((yield).upper()+'\n')

    >>> listener = zc.ngi.testing.listener('a', echo)

    >>> @zc.ngi.adapters.Lines.handler
    ... def client(connection):
    ...     connection.write('test\n')
    ...     response = (yield)
    ...     print 'client got', response

    >>> zc.ngi.testing.connect('a', client)
    client got TEST

    >>> listener.close()
    """

def testing_connection_processes_close_and_input_before_set_handler_in_order():
    r"""
If we are using test connections and the server sends input and closes
the connection before the client handler is set, the client must see the input:

    >>> @zc.ngi.adapters.Lines.handler
    ... def server(c):
    ...     c.write((yield).upper()+'\n')

    >>> listener = zc.ngi.testing.listener('x', server)

    >>> @zc.ngi.adapters.Lines.handler
    ... def client(c):
    ...     c.write('test\n')
    ...     print (yield)

    >>> zc.ngi.testing.connect('x', client)
    TEST

    >>> listener.close()
"""


def async_peer_address():
    r"""
    >>> @zc.ngi.adapters.Lines.handler
    ... def server(connection):
    ...     host, port = connection.peer_address
    ...     if not (host == '127.0.0.1' and isinstance(port, int)):
    ...         print 'oops', host, port
    ...     data = (yield)
    ...     connection.write(data+'\n')
    ...     listener.close()

    >>> listener = zc.ngi.async.listener(None, server)

    >>> @zc.ngi.adapters.Lines.handler
    ... def client(connection):
    ...     connection.write('hi\n')
    ...     yield

    >>> zc.ngi.async.connect(listener.address, client); zc.ngi.async.wait(1)

    """

def testing_peer_address():
    r"""
    >>> @zc.ngi.adapters.Lines.handler
    ... def server(connection):
    ...     print `connection.peer_address`
    ...     data = (yield)
    ...     connection.write(data+'\n')
    ...     listener.close()

    >>> listener = zc.ngi.testing.listener('', server)

    >>> @zc.ngi.adapters.Lines.handler
    ... def client(connection):
    ...     connection.write('hi\n')
    ...     yield

    >>> zc.ngi.testing.connect(listener.address, client,
    ...                        client_address=('xxx', 0))
    ('xxx', 0)

    Obscure:

    >>> conn = zc.ngi.testing.Connection(address='1', peer_address='2')
    >>> conn.peer_address, conn.peer.peer_address
    ('2', '1')

    >>> conn = zc.ngi.testing.Connection()
    >>> zc.ngi.testing.connectable('x', conn)
    >>> zc.ngi.testing.connect('x', client, client_address='y')
    -> 'hi\n'

    >>> conn.peer_address, conn.peer.peer_address
    ('x', 'y')

    """

def async_close_unix():
    """

When we create and the close a unix-domain socket, we remove the
socket file so we can reopen it later.

    >>> os.listdir('.')
    []

    >>> listener = zc.ngi.async.listener('socket', lambda c: None)
    >>> os.listdir('.')
    ['socket']

    >>> listener.close(); zc.ngi.async.wait(1)
    >>> os.listdir('.')
    []

    >>> listener = zc.ngi.async.listener('socket', lambda c: None)
    >>> os.listdir('.')
    ['socket']

    >>> listener.close(); zc.ngi.async.wait(1)
    >>> os.listdir('.')
    []

    """

def async_peer_address_unix():
    r"""
    >>> @zc.ngi.adapters.Lines.handler
    ... def server(connection):
    ...     print `connection.peer_address`
    ...     data = (yield)
    ...     connection.write(data+'\n')
    ...     listener.close()

    >>> listener = zc.ngi.async.listener('sock', server)

    >>> @zc.ngi.adapters.Lines.handler
    ... def client(connection):
    ...     connection.write('hi\n')
    ...     yield

    >>> zc.ngi.async.connect(listener.address, client); zc.ngi.async.wait(1)
    ''

    """

def async_bind_to_port_0():
    r"""

    When we bind to port 0, the listener has the actual address:

    >>> def server(conn):
    ...     conn.write('go away')
    ...     conn.close()

    >>> listener = zc.ngi.async.listener(('127.0.0.1', 0), server)
    >>> host, port = listener.address
    >>> host == '127.0.0.1' and port > 0
    True

    Make sure it works. :)

    >>> event = threading.Event()

    >>> @zc.ngi.generator.handler
    ... def client(conn):
    ...     print (yield)
    ...     event.set()

    >>> zc.ngi.async.connect(listener.address, client); _ = event.wait(1)
    go away
    """

if not hasattr(socket, 'AF_UNIX'):
    # windows
    del async_peer_address_unix, async_close_unix

if sys.version_info < (2, 6):
    del setHandler_compatibility

class BrokenConnect:

    connected = failed_connect = __call__ = lambda: xxxxx

class BrokenAfterConnect:

    def connected(self, connection):
        connection.write("Hee hee\0")
        connection.set_handler(self)

    __call__ = connected

    handle_input = handle_close = lambda: xxxxx

def setUp(test):
    cleanup()
    setupstack.setUpDirectory(test)
    setupstack.register(test, cleanup)

def async_evil_setup(test):
    setUp(test)

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

    port = zc.ngi.wordcount.start_server_process()
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

def cleanup():
    zc.ngi.testing._connectable.clear()
    zc.ngi.async.cleanup_map()
    zc.ngi.async.wait(9)

def test_suite():
    return unittest.TestSuite([
        manuel.testing.TestSuite(
            manuel.capture.Manuel() + manuel.doctest.Manuel(),
            'doc/index.txt',
            setUp=setUp, tearDown=setupstack.tearDown),
        doctest.DocFileSuite(
            'old.test',
            'testing.test',
            'message.test',
            'adapters.test',
            'blocking.test',
            'async-udp.test',
            setUp=setUp, tearDown=setupstack.tearDown),
        doctest.DocFileSuite(
            'async.test',
            setUp=async_evil_setup, tearDown=setupstack.tearDown,
            ),
        doctest.DocTestSuite(setUp=setUp, tearDown=setupstack.tearDown),
        ])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
