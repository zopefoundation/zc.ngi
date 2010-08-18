##############################################################################
#
# Copyright (c) 2006-2010 Zope Foundation and Contributors.
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
"""

import sys
import traceback
import warnings
import zc.ngi
import zc.ngi.interfaces

zc.ngi.interfaces.moduleProvides(zc.ngi.interfaces.IImplementation)

class PrintingHandler:

    def __init__(self, connection):
        connection.set_handler(self)

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

    zc.ngi.interfaces.implements(zc.ngi.interfaces.IConnection)

    def __init__(self, peer=None, handler=PrintingHandler,
                 address=None, peer_address=None):
        self.handler = None
        self.address = address
        self.handler_queue = []
        self.control = None
        self.closed = None
        if peer is None:
            peer = Connection(self, address=peer_address)
            handler(peer)
        self.peer = peer

    def __nonzero__(self):
        return not self.closed

    queue = None
    def _callHandler(self, method, arg):
        if self.handler is None:
            queue = self.handler_queue
            if (method == 'handle_input' and queue and queue[-1][0] == method):
                # combine inputs
                queue[-1] = method, queue[-1][1]+arg
            else:
                queue.append((method, arg))
            return

        if self.queue is None:
            self.queue = queue = [(method, arg)]
            while queue and not self.closed:
                method, arg = queue.pop(0)

                if method == 'handle_close':
                    if self.control is not None:
                        self.control.closed(self)
                    self.closed = arg

                try:
                    try:
                        handler = getattr(self.handler, method)
                    except AttributeError:
                        if method == 'handle_close':
                            return # Optional method
                        elif method == 'handle_exception':
                            # Unhandled exception
                            self.close()
                            handler = getattr(self.handler, 'handle_close',
                                              None)
                            if handler is None:
                                return
                            arg = 'unhandled exception'
                        else:
                            raise

                    handler(self, arg)
                except Exception, v:
                    print "Error test connection calling connection handler:"
                    traceback.print_exc(file=sys.stdout)
                    if method != 'handle_close':
                        self.close()
                        self.handler.handle_close(self, method+' error')

            self.queue = None
        else:
            self.queue.append((method, arg))

    def close(self):
        if self.closed:
            return
        self.peer.test_close('closed')
        if self.control is not None:
            self.control.closed(self)
        self.closed = True
        def write(s):
            raise TypeError("Connection closed")
        self.write = write

    def set_handler(self, handler):
        self.handler = handler
        while self.handler_queue:
            self._callHandler(*self.handler_queue.pop(0))

    def setHandler(self, handler):
        warnings.warn("setHandler is deprecated. Use set_handler,",
                      DeprecationWarning, stacklevel=2)
        self.set_handler(handler)

    def test_input(self, data):
        self._callHandler('handle_input', data)

    def test_close(self, reason):
        self._callHandler('handle_close', reason)

    def _exception(self, exception):
        self._callHandler('handle_exception', exception)

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

    @property
    def peer_address(self):
        return self.peer.address

class _ServerConnection(Connection):
    zc.ngi.interfaces.implements(zc.ngi.interfaces.IServerConnection)

    def __init__(self):
        Connection.__init__(self, False) # False to avoid setting peer handler
        self.peer = Connection(self)

class TextPrintingHandler(PrintingHandler):

    def handle_input(self, connection, data):
        print data,

def TextConnection(peer=None, handler=TextPrintingHandler):
    return Connection(peer, handler)

_connectable = {}
_recursing = object()
def connect(addr, handler, client_address=None):
    connections = _connectable.get(addr)
    if isinstance(connections, list):
        if connections:
            connection = connections.pop(0)
            connection.peer.address = addr
            connection.address = client_address
            return handler.connected(connection)
    elif isinstance(connections, listener):
        return connections.connect(handler=handler,
                                   client_address=client_address)
    elif connections is _recursing:
        print (
            "For address, %r, a connect handler called connect from a\n"
            "failed_connect call."
            % (addr, ))
        del _connectable[addr]
        return

    _connectable[addr] = _recursing
    handler.failed_connect('no such server')
    try:
        del _connectable[addr]
    except KeyError:
        pass

connector = connect

def connectable(addr, connection):
    _connectable.setdefault(addr, []).append(connection)


class listener:
    zc.ngi.interfaces.implements(zc.ngi.interfaces.IListener)

    def __init__(self, addr, handler=None):
        if handler is None:
            handler = addr
            addr = None
        else:
            _connectable[addr] = self
        self.address = addr
        self._handler = handler
        self._close_handler = None
        self._connections = []

    def connect(self, connection=None, handler=None, client_address=None):
        if self._handler is None:
            raise TypeError("Listener closed")

        try: # Round about None (or legacy addr) test
            connection.write
            orig = connection
        except AttributeError:
            connection = _ServerConnection()
            orig = None

        connection.control = self
        connection.peer.address = client_address
        connection.address = self.address
        self._connections.append(connection)
        self._handler(connection)

        if handler is not None:
            handler.connected(connection.peer)
        elif orig is None:
            PrintingHandler(connection.peer)
            return connection.peer

        return None

    connector = connect

    def connections(self):
        return iter(self._connections)

    def close(self, handler=None):
        if self.address is not None:
            del _connectable[self.address]
        self._handler = None
        if handler is None:
            while self._connections:
                self._connections[0].close()
        elif not self._connections:
            handler(self)
        else:
            self._close_handler = handler

    def closed(self, connection):
        self._connections.remove(connection)
        if not self._connections and self._close_handler:
            self._close_handler(self)

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


class test_udp_handler:

    def __init__(self, addr):
        self.addr = addr

    def __call__(self, addr, data):
        sys.stdout.write("udp from %r to %r:\n  %r" % (addr, self.addr, data))

_udp_handlers = {}
class udp_listener:
    zc.ngi.interfaces.implements(zc.ngi.interfaces.IUDPListener)

    def __init__(self, address, handler=None, buffer_size=4096):
        if handler is None:
            handler = test_udp_handler(address)
        self.address = address
        _udp_handlers[address] = handler, buffer_size

    def close(self):
        del _udp_handlers[self.address]

def udp(addr, data):
    handler = _udp_handlers.get(addr)
    if handler is None:
        return
    handler, buffer_size = handler
    if handler is not None:
        handler('<test>', data[:buffer_size])
