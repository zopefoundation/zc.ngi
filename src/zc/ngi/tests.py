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
import threading, unittest
from zope.testing import doctest
import zc.ngi.testing
import zc.ngi.async
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
    ...     zc.ngi.async.connector(addr, Handler())
    ...     lock.acquire()

    We find an unused port (so when we connect to it, the connection
    will fail).

    >>> port = zc.ngi.testing.get_port()

    Now let's try to connect

    >>> connect(('localhost', port))
    failed
    
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
    zc.ngi.async.connector(addr, BrokenConnect())

    # Start the server and connect to a good port with a bad handler

    port = zc.ngi.wordcount.start_server_process(zc.ngi.async.listener)
    addr = 'localhost', port
    zc.ngi.async.connector(addr, BrokenAfterConnect())

    # Stop the server
    zc.ngi.wordcount.stop_server_process(zc.ngi.async.connector, addr)

    # Create a lister with a broken server and connect to it
    port = zc.ngi.wordcount.get_port()
    addr = 'localhost', port
    zc.ngi.async.listener(addr, BrokenConnect())
    zc.ngi.async.connector(addr, BrokenAfterConnect())

    # Create a lister with a broken Server handler and connect to it
    port = zc.ngi.wordcount.get_port()
    addr = 'localhost', port
    zc.ngi.async.listener(addr, BrokenAfterConnect())
    zc.ngi.async.connector(addr, BrokenAfterConnect())

    
def test_suite():
    return unittest.TestSuite([
        doctest.DocFileSuite(
            'README.txt',
            'message.txt',
            'adapters.txt',
            'blocking.txt',
            ),
        doctest.DocFileSuite(
            'async.txt',
            setUp=async_evil_setup,
            ),
        doctest.DocTestSuite(),
        ])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
