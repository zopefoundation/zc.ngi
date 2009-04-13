##############################################################################
#
# Copyright (c) 2006 Zope Corporation and Contributors.
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
"""Testing NGI implementation

$Id$
"""

import sys
import traceback
import zc.ngi

class PrintingHandler:

    def __init__(self, connection):
        connection.setHandler(self)

    def handle_input(self, connection, data):
        data = repr(data)
        print '->', data[:50]
        data = data[50:]
        while data:
            print '.>', data[:50]
            data = data[50:]

    def handle_close(self, connection, reason):
        if reason != 'closed':
            print '-> CLOSE', reason
        else:
            print '-> CLOSE'

    def handle_exception(self, connection, exception):
        print '-> EXCEPTION', exception.__class__.__name__, exception

class Connection:

    control = None

    def __init__(self, peer=None, handler=PrintingHandler):
        self.handler = None
        self.closed = False
        self.input = ''
        self.exception = None
        if peer is None:
            peer = Connection(self)
            handler(peer)d
        self.peer = peer

    def __nonzero__(self):
        return not self.closed

    queue = None
    def _callHandler(self, method, *args):
        if self.queue is None:
            self.queue = [(method, args)]
            while self.queue:
                method, args = self.queue.pop(0)
                if self.closed and method != 'handle_close':
                    break
                try:
                    getattr(self.handler, method)(self, *args)
                except:
                    print "Error test connection calling connection handler:"
                    traceback.print_exc(file=sys.stdout)
                    if method != 'handle_close':
                        self.close()
                        self.handler.handle_close(self, method+' error')

            self.queue = None
        else:
            self.queue.append((method, args))

    def close(self):
        self.peer.test_close('closed')
        if self.control is not None:
            self.control.closed(self)
        self.closed = True
        def write(s):
            raise TypeError("Connection closed")
        self.write = write

    def setHandler(self, handler):
        self.handler = handler
        if self.exception:
            exception = self.exception
            self.exception = None
            self._callHandler('handle_exception', exception)
        if self.input:
            self._callHandler('handle_input', self.input)
            self.input = ''

        # Note is self.closed is True, we self closed and we
        # don't want to call handle_close.
        if self.closed and isinstance(self.closed, str):
            self._callHandler('handle_close', self.closed)

    def test_input(self, data):
        if self.handler is not None:
            self._callHandler('handle_input', data)
        else:
            self.input += data

    def test_close(self, reason):
        if self.control is not None:
            self.control.closed(self)
        self.closed = reason
        if self.handler is not None:
            self._callHandler('handle_close', reason)

    def write(self, data):
        if data is zc.ngi.END_OF_DATA:
            return self.close()

        if isinstance(data, str):
            self.peer.test_input(data)
        else:
            raise TypeError("write argument must be a string")

    def writelines(self, data):
        assert not (isinstance(data, str) or (data is zc.ngi.END_OF_DATA))
        data = iter(data)
        try:
            for d in data:
                if not isinstance(d, str):
                    raise TypeError("Got a non-string result from iterable")
                self.write(d)
        except Exception, v:
            self._exception(v)

    def _exception(self, exception):
        if self.handler is None:
            self.exception = exception
        else:
            self._callHandler('handle_exception', exception)

class TextPrintingHandler(PrintingHandler):

    def handle_input(self, connection, data):
        print data,

class TextConnection(Connection):

    control = None

    def __init__(self, peer=None, handler=TextPrintingHandler):
        Connection.__init__(self, peer, handler)

_connectable = {}

def connector(addr, handler):
    connections = _connectable.get(addr)
    if connections:
        handler.connected(connections.pop(0))
    else:
        handler.failed_connect('no such server')

def connectable(addr, connection):
    _connectable.setdefault(addr, []).append(connection)

class listener:

    def __init__(self, handler):
        self._handler = handler
        self._close_handler = None
        self._connections = []

    def connect(self, connection):
        if self._handler is None:
            raise TypeError("Listener closed")
        self._connections.append(connection)
        connection.control = self
        self._handler(connection)

    def connections(self):
        return iter(self._connections)

    def close(self, handler=None):
        self._handler = None
        if handler is None:
            while self._connections:
                self._connections[0].test_close('stopped')
        elif not self._connections:
            handler(self)
        else:
            self._close_handler = handler

    def closed(self, connection):
        self._connections.remove(connection)
        if not self._connections and self._close_handler:
            self._close_handler(self)

    def connector(self, addr, handler):
        handler.connected(Connection(None, self._handler))


class peer:

    def __init__(self, addr, handler):
        self.addr = addr
        self.handler = handler

    def __call__(self, addr, handler):
        if addr != self.addr:
            handler.failed_connect('connection refused')
        else:
            handler.connected(Connection(None, self.handler))

# XXX This should move to zope.testing
import random, socket
def get_port():
    """Return a port that is not in use.

    Checks if a port is in use by trying to connect to it.  Assumes it
    is not in use if connect raises an exception.

    Raises RuntimeError after 10 tries.
    """
    for i in range(10):
        port = random.randrange(20000, 30000)
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            try:
                s.connect(('localhost', port))
            except socket.error:
                # Perhaps we should check value of error too.
                return port
        finally:
            s.close()
    raise RuntimeError("Can't find port")
