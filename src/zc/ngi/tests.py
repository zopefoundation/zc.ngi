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
"""XXX short summary goes here.

$Id$
"""
from zope.testing import doctest
import manuel.capture
import manuel.doctest
import manuel.testing
import threading, unittest
import zc.ngi.async
import zc.ngi.testing
import zc.ngi.wordcount

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
