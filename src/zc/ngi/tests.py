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
import unittest
from zope.testing import doctest
import zc.ngi.testing
import zc.ngi.async # start async thread before tests run

def test_async_cannot_connect():
    """Let's make sure that the connector handles connection failures correctly

    >>> import threading
    >>> lock = threading.Lock()
    >>> _ = lock.acquire()

    We define a simple handler that just notifies of failed connectioons.

    >>> class Handler:
    ...     def failed_connect(connection, reason):
    ...         print 'failed', reason
    ...         lock.release()

    >>> def connect(addr):
    ...     zc.ngi.async.connector(addr, Handler())
    ...     lock.acquire()

    We find an unused port (so when we connect to it, the connection
    will fail).

    >>> port = zc.ngi.testing.get_port()

    Now let's try to connect

    >>> connect(('localhost', port))
    failed connection failed
    
    """

def test_suite():
    return unittest.TestSuite([
        doctest.DocFileSuite(
            'README.txt',
            'message.txt',
            'async.txt',
            'adapters.txt',
            ),
        doctest.DocTestSuite(),
        ])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
