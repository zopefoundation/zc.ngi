##############################################################################
#
# Copyright (c) 2006 Zope Foundation and Contributors.
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
"""Asyncore-based implementation of the NGI
"""
from __future__ import with_statement

import asyncore
import errno
import logging
import os
import socket
import sys
import thread
import threading
import time
import warnings
import zc.ngi
import zc.ngi.interfaces

zc.ngi.interfaces.moduleProvides(zc.ngi.interfaces.IImplementation)

pid = os.getpid()
is_win32 = sys.platform == 'win32'

expected_socket_read_errors = {
    errno.EWOULDBLOCK: 0,
    errno.EAGAIN: 0,
    errno.EINTR: 0,
    }

expected_socket_write_errors = {
    errno.EAGAIN: 0,
    errno.EWOULDBLOCK: 0,
    errno.ENOBUFS: 0,
    errno.EINTR: 0,
    }

BUFFER_SIZE = 8*1024

class Implementation:
    zc.ngi.interfaces.implements(zc.ngi.interfaces.IImplementation)

    logger = logging.getLogger('zc.ngi.async.Implementation')

    def __init__(self, daemon=True, name='zc.ngi.async application created'):
        self.name = name
        self.daemon = daemon
        self._map = {}
        self._callbacks = []
        self._start_lock = threading.Lock()

    thread_ident = None
    def call_from_thread(self, func):
        if thread.get_ident() == self.thread_ident:
            func()
            return
        self._callbacks.append(func)
        self.notify_select()
        self.start_thread()

    def notify_select(self):
        pass

    def connect(self, addr, handler):
        self.call_from_thread(lambda : _Connector(addr, handler, self))
        self.start_thread()

    def listener(self, addr, handler, thready=False):
        result = _Listener(addr, handler, self, thready)
        self.start_thread()
        return result

    def udp(self, address, message):
        if isinstance(address, str):
            family = socket.AF_UNIX
        else:
            family = socket.AF_INET
        try:
            sock = _udp_socks[family].pop()
        except IndexError:
            sock = socket.socket(family, socket.SOCK_DGRAM)

        sock.sendto(message, address)
        _udp_socks[family].append(sock)

    def udp_listener(self, addr, handler, buffer_size=4096):
        result = _UDPListener(addr, handler, buffer_size, self)
        self.start_thread()
        return result

    _thread = None
    def start_thread(self):
        with self._start_lock:
            if self._thread is None:
                self._thread = threading.Thread(
                    target=self.loop, name=self.name)
                self._thread.setDaemon(self.daemon)
                self._thread.start()

    def wait(self, timeout=None):
        with self._start_lock:
            if self._thread is None:
                return
            join = self._thread.join
        join(timeout)
        if self._thread is not None:
            raise zc.ngi.interfaces.Timeout

    def loop(self, timeout=None):
        self.thread_ident = thread.get_ident()
        if timeout is not None:
            deadline = time.time() + timeout
        else:
            deadline = None
            timeout = 30
        map = self._map
        callbacks = self._callbacks
        logger = logging.getLogger('zc.ngi.async.loop')
        trigger = _Trigger(self._map)
        self.notify_select = trigger.pull_trigger

        try:
            while 1:

                while callbacks:
                    callback = callbacks.pop(0)
                    try:
                        callback()
                    except:
                        self.logger.exception('Calling callback')
                        self.handle_error()

                if deadline:
                    timeout = min(deadline - time.time(), 30)

                try:
                    if (timeout > 0) and (len(map) > 1):
                        asyncore.poll(timeout, map)
                except:
                    logger.exception('loop error')
                    raise

                if trigger._fileno is None:
                    # oops, the trigger got closed.  Recreate it.
                    trigger = _Trigger(self._map)
                    self.notify_select = trigger.pull_trigger

                with self._start_lock:
                    if (len(map) <= 1) and not callbacks:
                        self._thread = None
                        return

                if timeout <= 0:
                    raise zc.ngi.interfaces.Timeout
        finally:
            del self.thread_ident
            del self.notify_select
            trigger.close()

    def cleanup_map(self):
        for c in self._map.values():
            if isinstance(c, _Trigger):
                continue
            c.close()
        for c in self._map.values():
            if isinstance(c, _Trigger):
                continue
            c.close()

    def handle_error(self):
        pass

class Inline(Implementation):
    """Run in an application thread, rather than a separate thread.
    """

    logger = logging.getLogger('zc.ngi.async.Inline')

    def start_thread(self):
        pass

    def handle_error(self):
        raise

    def wait(self, *args):
        self.loop(*args)

class dispatcher(asyncore.dispatcher):

    def __init__(self, sock, addr, implementation):
        self.addr = addr
        self.implementation = implementation
        asyncore.dispatcher.__init__(self, sock, implementation._map)

    def handle_error(self):
        reason = sys.exc_info()[1]
        self.logger.exception('handle_error')
        try:
            self.handle_close(reason)
        except:
            self.logger.exception(
                "Exception raised by dispatcher handle_close(%r)",
                reason)
            self.close()
        self.implementation.handle_error()

    def close(self):
        self.del_channel(self._map)
        self.implementation.call_from_thread(self.socket.close)

    def writable(self):
        return False

class _ConnectionDispatcher(dispatcher):

    __closed = None
    __handler = None
    __iterator_exception = None
    _connection = None

    def __init__(self, sock, addr, logger, implementation):
        self.__output = []
        dispatcher.__init__(self, sock, addr, implementation)
        self.logger = logger

    def __nonzero__(self):
        return self.__output is not None

    def set_handler(self, handler):
        if self.__handler is not None:
            raise TypeError("Handler already set")

        self.__handler = handler
        if self.__iterator_exception:
            v = self.__iterator_exception
            self.__iterator_exception = None
            try:
                handler.handle_exception(self, v)
            except:
                self.logger.exception("handle_exception failed")
                raise

        if self.__closed:
            try:
                handler.handle_close(self._connection, self.__closed)
            except:
                self.logger.exception("Exception raised by handle_close(%r)",
                                      self.__closed)
                raise

    def setHandler(self, handler):
        warnings.warn("setHandler is deprecated. Use set_handler,",
                      DeprecationWarning, stacklevel=2)
        self.set_handler(handler)

    def write(self, data):
        if __debug__:
            self.logger.debug('write %r', data)
        assert isinstance(data, str) or (data is zc.ngi.END_OF_DATA)
        try:
            self.__output.append(data)
        except AttributeError:
            if self.__output is None:
                raise ValueError("write called on closed connection")
            raise
        self.implementation.notify_select()

    def writelines(self, data):
        if __debug__:
            self.logger.debug('writelines %r', data)
        assert not isinstance(data, str), "writelines does not accept strings"
        try:
            self.__output.append(iter(data))
        except AttributeError:
            if self.__output is None:
                raise ValueError("writelines called on closed connection")
            raise
        self.implementation.notify_select()

    def close_after_write(self):
        try:
            self.__output.append(zc.ngi.END_OF_DATA)
        except AttributeError:
            if self.__output is None:
                return # already closed
            raise
        self.implementation.notify_select()

    def close(self):
        self.__output = None
        dispatcher.close(self)
        self.implementation.notify_select()

    def readable(self):
        return self.__handler is not None

    def writable(self):
        return bool(self.__output)

    def handle_read_event(self):
        assert self.readable()

        while 1:
            try:
                d = self.recv(BUFFER_SIZE)
            except socket.error, err:
                if err[0] in expected_socket_read_errors:
                    return
                raise

            if not d:
                return

            if __debug__:
                self.logger.debug('input %r', d)
            try:
                self.__handler.handle_input(self._connection, d)
            except:
                self.logger.exception("handle_input failed")
                raise

            if len(d) < BUFFER_SIZE:
                break

    def handle_write_event(self):
        if __debug__:
            self.logger.debug('handle_write_event')

        tosend = []
        nsend = 0
        send_size = 60000
        output = self.__output
        try:
            while output:
                v = output[0]
                if v is zc.ngi.END_OF_DATA:
                    if not nsend:
                        self.close()
                        return
                    send_size = 0
                elif isinstance(v, str):
                    tosend.append(v)
                    nsend += len(v)
                    output.pop(0)
                else:
                    # Must be an iterator
                    try:
                        v = v.next()
                        if not isinstance(v, str):
                            raise TypeError(
                                "writelines iterator must return strings", v)
                    except StopIteration:
                        # all done
                        output.pop(0)
                    except Exception, v:
                        self.logger.exception("writelines iterator failed")
                        if self.__handler is None:
                            self.__iterator_exception = v
                        else:
                            self.__handler.handle_exception(self._connection, v)
                        raise
                    else:
                        tosend.append(v)
                        nsend += len(v)

                if output and nsend < send_size:
                    continue

                v = ''.join(tosend)
                try:
                    n = self.send(v)
                except socket.error, err:
                    if err[0] in expected_socket_write_errors:
                        return # we couldn't write anything
                    raise
                except Exception, v:
                    self.logger.exception("send failed")
                    raise

                if n == nsend:
                    nsend = 0
                    del tosend[:]
                else:
                    nsend -= n
                    tosend[:] = v[n:],
                    return # can't send any more
        finally:
            if nsend:
                output[0:0] = tosend


    def handle_close(self, reason='end of input'):
        if __debug__:
            self.logger.debug('close %r', reason)
        if self.__handler is not None:
            try:
                self.__handler.handle_close(self._connection, reason)
            except:
                self.logger.exception("Exception raised by handle_close(%r)",
                                      reason)
        else:
            self.__closed = reason
        self.close()

    def handle_expt(self):
        self.handle_close('socket error')

    def __hash__(self):
        return hash(self.socket)

class _ServerConnectionDispatcher(_ConnectionDispatcher):

    def __init__(self, control, *args):
        self.control = control
        _ConnectionDispatcher.__init__(self, *args)

    def close(self):
        _ConnectionDispatcher.close(self)
        self.control.closed(self._connection)

class _Connection:
    zc.ngi.interfaces.implements(zc.ngi.interfaces.IConnection)

    def __init__(self, dispatcher):
        self._dispatcher = dispatcher
        dispatcher._connection = self

    def __nonzero__(self):
        return bool(self._dispatcher)

    def set_handler(self, handler):
        return self._dispatcher.set_handler(handler)

    def setHandler(self, handler):
        warnings.warn("setHandler is deprecated. Use set_handler,",
                      DeprecationWarning, stacklevel=2)
        self.set_handler(handler)

    def write(self, data):
        write = self._dispatcher.write
        self.write = write
        write(data)

    def writelines(self, data):
        writelines = self._dispatcher.writelines
        self.writelines = writelines
        writelines(data)

    def close(self):
        self._dispatcher.close_after_write()

    @property
    def peer_address(self):
        return self._dispatcher.socket.getpeername()

class _ServerConnection(_Connection):
    zc.ngi.interfaces.implements(zc.ngi.interfaces.IServerConnection)

    @property
    def control(self):
        return self._dispatcher.control

class _Connector(dispatcher):

    logger = logging.getLogger('zc.ngi.async.client')

    # When trying to do a connect on a non-blocking socket, some outcomes
    # are expected.  Set _CONNECT_IN_PROGRESS to the errno value(s) expected
    # when an initial connect can't complete immediately.  Set _CONNECT_OK
    # to the errno value(s) expected if the connect succeeds *or* if it's
    # already connected (our code can attempt redundant connects).
    if hasattr(errno, "WSAEWOULDBLOCK"):    # Windows
        # Caution:  The official Winsock docs claim that WSAEALREADY should be
        # treated as yet another "in progress" indicator, but we've never
        # seen this.
        _CONNECT_IN_PROGRESS = (errno.WSAEWOULDBLOCK,)
        # Win98: WSAEISCONN; Win2K: WSAEINVAL
        _CONNECT_OK          = (0, errno.WSAEISCONN, errno.WSAEINVAL)
    else:                                   # Unix
        _CONNECT_IN_PROGRESS = (errno.EINPROGRESS,)
        _CONNECT_OK          = (0, errno.EISCONN)

    def __init__(self, addr, handler, implementation):
        self.__handler = handler
        if isinstance(addr, str):
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        else:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        dispatcher.__init__(self, sock, addr, implementation)

        if __debug__:
            self.logger.debug('connecting to %s', self.addr)

        # INVARIANT: we are called from the select thread!

        try:
            self.handle_write_event()
        except:
            self.handle_error()

    def readable(self):
        return False

    def writable(self):
        return True

    def handle_close(self, reason=None):
        if __debug__:
            self.logger.debug('connector close %r', reason)
        try:
            try:
                self.__handler.failed_connect(reason)
            except:
                self.logger.exception("failed_connect(%r) failed", reason)
                self.implementation.handle_error()
        finally:
            self.close()

    def handle_write_event(self):
        err = self.socket.connect_ex(self.addr)
        if err in self._CONNECT_IN_PROGRESS:
            return

        if err not in self._CONNECT_OK:
            reason = errno.errorcode.get(err) or str(err)
            self.logger.warning("error connecting to %s: %s", self.addr, reason)
            self.handle_close(reason)
            return

        self.del_channel(self._map)
        if __debug__:
            self.logger.debug('outgoing connected %r', self.addr)

        dispatcher = _ConnectionDispatcher(self.socket, self.addr, self.logger,
                                           self.implementation)
        try:
            self.__handler.connected(_Connection(dispatcher))
        except:
            self.logger.exception("connection handler failed")
            dispatcher.handle_close("connection handler failed")
        return

    def handle_error(self):
        reason = sys.exc_info()[1]
        self.logger.exception('connect error')
        try:
            self.__handler.failed_connect(reason)
        except:
            self.logger.exception(
                "Handler failed_connect(%s) raised an exception", reason,
                )
        self.close()
        self.implementation.handle_error()

    def handle_expt(self):
        self.handle_close('connection failed')

class BaseListener(asyncore.dispatcher):

    def __init__(self, implementation):
        self.implementation = implementation
        asyncore.dispatcher.__init__(self, map=implementation._map)

    def writable(self):
        return False

    def add_channel(self, map=None):
        # work around file-dispatcher bug
        if map is None:
            return
        assert (map is self._map)
        asyncore.dispatcher.add_channel(self, self._map)

    def handle_error(self):
        reason = sys.exc_info()[1]
        self.logger.exception('listener error')
        self.close()
        self.implementation.handle_error()

class _Listener(BaseListener):
    zc.ngi.interfaces.implements(zc.ngi.interfaces.IListener)

    logger = logging.getLogger('zc.ngi.async.server')

    def __init__(self, addr, handler, implementation, thready):
        self.__handler = handler
        self.__close_handler = None
        self._thready = thready
        self.__connections = set()
        self.address = addr
        BaseListener.__init__(self, implementation)
        if isinstance(addr, str):
            family = socket.AF_UNIX
        else:
            family = socket.AF_INET
        self.create_socket(family, socket.SOCK_STREAM)
        try:
            if not is_win32:
                self.set_reuse_addr()
            if addr is None:
                # Try to pick one, primarily for testing
                import random
                n = 0
                while 1:
                    port = random.randint(10000, 30000)
                    addr = 'localhost', port
                    try:
                        self.bind(addr)
                    except socket.error:
                        n += 1
                        if n > 100:
                            raise
                        else:
                            continue
                    break
            else:
                self.bind(addr)
                if family is socket.AF_INET and addr[1] == 0:
                    self.addr = addr = addr[0], self.socket.getsockname()[1]

            self.logger.info("listening on %r", addr)
            self.listen(255)
        except socket.error:
            self.close()
            self.logger.warn("unable to listen on %r", addr)
            raise

        self.add_channel(self._map)
        self.address = addr
        self.implementation.notify_select()

    def handle_accept(self):
        if not self.accepting:
            return

        try:
            r = self.accept()
            if r:
                sock, addr = r
            else:
                # didn't get anything. Hm. Ignore.
                return
        except socket.error, msg:
            self.logger.exception("accepted failed: %s", msg)
            return
        if __debug__:
            self.logger.debug('incoming connection %r', addr)

        if self._thready:
            impl = Implementation(name="%r client" % (self.address,))
        else:
            impl = self.implementation

        dispatcher = _ServerConnectionDispatcher(
            self, sock, addr, self.logger, impl)
        connection = _ServerConnection(dispatcher)
        self.__connections.add(connection)

        @impl.call_from_thread
        def _():
            try:
                self.__handler(connection)
            except:
                self.logger.exception("server handler failed")
                self.close()

        if impl is not self.implementation:
            impl.start_thread()


    def connections(self):
        return iter(self.__connections)

    def closed(self, connection):
        if connection in self.__connections:
            self.__connections.remove(connection)
            if not self.__connections and self.__close_handler:
                self.__close_handler(self)

    def _close(self, handler):
        BaseListener.close(self)
        if isinstance(self.address, str) and os.path.exists(self.address):
            os.remove(self.address)

        if handler is None:
            for c in list(self.__connections):
                c._dispatcher.handle_close("stopped")
        elif not self.__connections:
            handler(self)
        else:
            self.__close_handler = handler

    def close(self, handler=None):
        self.accepting = False
        self.implementation.call_from_thread(lambda : self._close(handler))

    def close_wait(self, timeout=None):
        event = threading.Event()
        self.close(lambda _: event.set())
        event.wait(timeout)

    # convenience method made possible by storing our address:
    def connect(self, handler):
        self.implementation.connect(self.address, handler)

class _UDPListener(BaseListener):

    logger = logging.getLogger('zc.ngi.async.udpserver')
    connected = True

    def __init__(self, addr, handler, buffer_size, implementation):
        self.__handler = handler
        self.__buffer_size = buffer_size
        BaseListener.__init__(self, implementation)
        if isinstance(addr, str):
            family = socket.AF_UNIX
        else:
            family = socket.AF_INET
        try:
            self.create_socket(family, socket.SOCK_DGRAM)
            if not is_win32:
                self.set_reuse_addr()
            self.bind(addr)
            self.logger.info("listening on udp %r", addr)
        except socket.error:
            self.close()
            self.logger.warn("unable to listen on udp %r", addr)
            raise
        self.add_channel(self._map)
        self.implementation.notify_select()

    def handle_read(self):
        message, addr = self.socket.recvfrom(self.__buffer_size)
        self.__handler(addr, message)

    def close(self):
        self.del_channel(self._map)
        self.implementation.call_from_thread(self.socket.close)

# udp uses GIL to get thread-safe socket management
if is_win32:
    _udp_socks = {socket.AF_INET: []}
else:
    _udp_socks = {socket.AF_INET: [], socket.AF_UNIX: []}

# The following trigger code is greatly simplified from the Medusa
# trigger code.

class _Triggerbase(object):
    """OS-independent base class for OS-dependent trigger class."""

    logger = logging.getLogger('zc.ngi.async.trigger')

    def writable(self):
        return 0

    def handle_close(self):
        self.close()

    def handle_error(self):
        self.logger.exception('trigger error %s', pid)
        self.close()

    def handle_read(self):
        try:
            self.recv(BUFFER_SIZE)
        except socket.error:
            pass

if os.name == 'posix':

    class _Trigger(_Triggerbase, asyncore.file_dispatcher):
        def __init__(self, map):
            r, self.__writefd = os.pipe()
            asyncore.file_dispatcher.__init__(self, r, map)

            if self.socket.fd != r:
                # Starting in Python 2.6, the descriptor passed to
                # file_dispatcher gets duped and assigned to
                # self.fd. This breaks the instantiation semantics and
                # is a bug imo.  I dount it will get fixed, but maybe
                # it will. Who knows. For that reason, we test for the
                # fd changing rather than just checking the Python version.
                os.close(r)

        def close(self):
            os.close(self.__writefd)
            asyncore.file_dispatcher.close(self)

        def pull_trigger(self):
            if __debug__:
                self.logger.debug('pulled %s', pid)
            os.write(self.__writefd, 'x')

        def add_channel(self, map=None):
            # work around file-dispatcher bug
            assert (map is None) or (map is self._map)
            asyncore.dispatcher.add_channel(self, self._map)

else:
    # Windows version; uses just sockets, because a pipe isn't select'able
    # on Windows.

    class BindError(Exception):
        pass

    class _Trigger(_Triggerbase, asyncore.dispatcher):
        def __init__(self, map):
            # Get a pair of connected sockets.  The trigger is the 'w'
            # end of the pair, which is connected to 'r'.  'r' is put
            # in the asyncore socket map.  "pulling the trigger" then
            # means writing something on w, which will wake up r.

            w = socket.socket()
            # Disable buffering -- pulling the trigger sends 1 byte,
            # and we want that sent immediately, to wake up asyncore's
            # select() ASAP.
            w.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

            count = 0
            while 1:
               count += 1
               # Bind to a local port; for efficiency, let the OS pick
               # a free port for us.
               # Unfortunately, stress tests showed that we may not
               # be able to connect to that port ("Address already in
               # use") despite that the OS picked it.  This appears
               # to be a race bug in the Windows socket implementation.
               # So we loop until a connect() succeeds (almost always
               # on the first try).  See the long thread at
               # http://mail.zope.org/pipermail/zope/2005-July/160433.html
               # for hideous details.
               a = socket.socket()
               a.bind(("127.0.0.1", 0))
               connect_address = a.getsockname()  # assigned (host, port) pair
               a.listen(1)
               try:
                   w.connect(connect_address)
                   break    # success
               except socket.error, detail:
                   if detail[0] != errno.WSAEADDRINUSE:
                       # "Address already in use" is the only error
                       # I've seen on two WinXP Pro SP2 boxes, under
                       # Pythons 2.3.5 and 2.4.1.
                       raise
                   # (10048, 'Address already in use')
                   # assert count <= 2 # never triggered in Tim's tests
                   if count >= 10:  # I've never seen it go above 2
                       a.close()
                       w.close()
                       raise BindError("Cannot bind trigger!")
                   # Close `a` and try again.  Note:  I originally put a short
                   # sleep() here, but it didn't appear to help or hurt.
                   a.close()

            r, addr = a.accept()  # r becomes asyncore's (self.)socket
            a.close()
            self.trigger = w
            asyncore.dispatcher.__init__(self, r, map)

        def close(self):
            self.del_channel(self._map)
            # self.socket is r, and self.trigger is w, from __init__
            self.socket.close()
            self.trigger.close()

        def pull_trigger(self):
            if __debug__:
                self.logger.debug('notify select %s', pid)
            self.trigger.send('x')

_select_implementation = Implementation(name=__name__)

call_from_thread = _select_implementation.call_from_thread
connect = connector = _select_implementation.connect
listener = _select_implementation.listener
start_thread = _select_implementation.start_thread
udp = _select_implementation.udp
udp_listener = _select_implementation.udp_listener
_map = _select_implementation._map
cleanup_map = _select_implementation.cleanup_map
wait = _select_implementation.wait

main = Inline()
