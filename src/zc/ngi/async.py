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
"""Asyncore-based implementation of the NGI

$Id$
"""

import asyncore
import errno
import logging
import os
import select
import socket
import sys
import threading
import time

import zc.ngi

pid = os.getpid()

_map = {}
_connectors = {}

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

class dispatcher(asyncore.dispatcher):

    def __init__(self, sock, addr, map=_map):
        self.addr = addr
        asyncore.dispatcher.__init__(self, sock, map)

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

    def close(self):
        self.del_channel(_map)
        self.socket.close()

    def writable(self):
        return False

class _Connection(dispatcher):

    control = None

    def __init__(self, sock, addr, logger):
        self.__connected = True
        self.__closed = None
        self.__handler = None
        self.__exception = None
        self.__output = []
        dispatcher.__init__(self, sock, addr)
        self.logger = logger

    def __nonzero__(self):
        return self.__connected

    def setHandler(self, handler):
        if self.__handler is not None:
            raise TypeError("Handler already set")

        self.__handler = handler
        if self.__exception:
            exception = self.__exception
            self.__exception = None
            try:
                handler.handle_exception(self, exception)
            except:
                self.logger.exception("handle_exception failed")
                return self.handle_close("handle_exception failed")

        if self.__closed:
            try:
                handler.handle_close(self, self.__closed)
            except:
                self.logger.exception("Exception raised by handle_close(%r)",
                                      self.__closed)
                raise

    def write(self, data):
        if __debug__:
            self.logger.debug('write %r', data)
        assert isinstance(data, str) or (data is zc.ngi.END_OF_DATA)
        self.__output.append(data)
        notify_select()

    def writelines(self, data):
        if __debug__:
            self.logger.debug('writelines %r', data)
        assert not isinstance(data, str), "writelines does not accept strings"
        self.__output.append(iter(data))
        notify_select()

    def close(self):
        self.__connected = False
        self.__output[:] = []
        dispatcher.close(self)
        if self.control is not None:
            self.control.closed(self)
        notify_select()

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
                self.__handler.handle_input(self, d)
            except:
                self.logger.exception("handle_input failed")
                self.handle_close("handle_input failed")

            if len(d) < BUFFER_SIZE:
                break

    def handle_write_event(self):
        if __debug__:
            self.logger.debug('handle_write_event')

        while self.__output:
            output = self.__output
            v = output[0]
            if v is zc.ngi.END_OF_DATA:
                self.close()
                return

            if not isinstance(v, str):
                # Must be an iterator
                try:
                    v = v.next()
                except StopIteration:
                    # all done
                    output.pop(0)
                    continue

                if __debug__ and not isinstance(v, str):
                    exc = TypeError("iterable output returned a non-string", v)
                    self.__report_exception(exc)
                    raise exc

                output.insert(0, v)

            if not v:
                output.pop(0)
                continue

            try:
                n = self.send(v)
            except socket.error, err:
                if err[0] in expected_socket_write_errors:
                    return # we couldn't write anything
                raise
            except Exception, v:
                self.__report_exception(v)
                raise

            if n == len(v):
                output.pop(0)
            else:
                output[0] = v[n:]
                return # can't send any more

    def __report_exception(self, exception):
        if self.__handler is not None:
            try:
                self.__handler.handle_exception(self, exception)
            except:
                self.logger.exception("handle_exception failed")
                self.handle_close("handle_exception failed")
        else:
            self.__exception = exception

    def handle_close(self, reason='end of input'):
        if __debug__:
            self.logger.debug('close %r', reason)
        if self.__handler is not None:
            try:
                self.__handler.handle_close(self, reason)
            except:
                self.logger.exception("Exception raised by handle_close(%r)",
                                      reason)
        else:
            self.__closed = reason
        self.close()

    def handle_expt(self):
        self.handle_close('socket error')


class connector(dispatcher):

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

    def __init__(self, addr, handler):
        self.__handler = handler
        if isinstance(addr, str):
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        else:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        dispatcher.__init__(self, sock, addr, _connectors)

        notify_select()

    def connect(self):
        if __debug__:
            self.logger.debug('connecting to %s', self.addr)

        self.add_channel(_map)
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
            self.__handler.failed_connect(reason)
        except:
            self.logger.exception("failed_connect(%r) failed", reason)
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

        self.del_channel(_map)
        if __debug__:
            self.logger.debug('outgoing connected %r', self.addr)

        connection = _Connection(self.socket, self.addr, self.logger)
        try:
            self.__handler.connected(connection)
        except:
            self.logger.exception("connection handler failed")
            connection.handle_close("connection handler failed")
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

    def handle_expt(self):
        self.handle_close('connection failed')

class listener(asyncore.dispatcher):

    logger = logging.getLogger('zc.ngi.async.server')

    def __init__(self, addr, handler):
        self.addr = addr
        self.__handler = handler
        self.__close_handler = None
        self.__connections = {}
        asyncore.dispatcher.__init__(self)
        if isinstance(addr, str):
            self.create_socket(socket.AF_UNIX, socket.SOCK_STREAM)
        else:
            self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.set_reuse_addr()
        self.logger.info("listening on %s", self.addr)
        self.bind(self.addr)
        self.listen(255)
        notify_select()

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

        connection = _Connection(sock, addr, self.logger)
        self.__connections[connection] = 1
        connection.control = self
        try:
            self.__handler(connection)
        except:
            self.logger.exception("server handler failed")
            self.close()

    def connections(self):
        return iter(self.__connections)

    def closed(self, connection):
        if connection in self.__connections:
            del self.__connections[connection]
            if not self.__connections and self.__close_handler:
                self.__close_handler(self)

    def close(self, handler=None):
        self.accepting = False
        self.del_channel(_map)
        self.socket.close()
        if handler is None:
            for c in list(self.__connections):
                c.handle_close("stopped")
        elif not self.__connections:
            handler(self)
        else:
            self.__close_handler = handler

    def add_channel(self, map=None):
        # work around file-dispatcher bug
        assert (map is None) or (map is _map)
        asyncore.dispatcher.add_channel(self, _map)

    def handle_error(self):
        reason = sys.exc_info()[1]
        self.logger.exception('listener error')
        self.close()

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
            return

if os.name == 'posix':

    class _Trigger(_Triggerbase, asyncore.file_dispatcher):
        def __init__(self):
            self.__readfd, self.__writefd = os.pipe()
            asyncore.file_dispatcher.__init__(self, self.__readfd)

        def close(self):
            self.del_channel(_map)
            os.close(self.__writefd)
            os.close(self.__readfd)

        def pull_trigger(self):
            if __debug__:
                self.logger.debug('pulled %s', pid)
            os.write(self.__writefd, 'x')

        def add_channel(self, map=None):
            # work around file-dispatcher bug
            assert (map is None) or (map is _map)
            asyncore.dispatcher.add_channel(self, _map)

else:
    # Windows version; uses just sockets, because a pipe isn't select'able
    # on Windows.

    class _Trigger(_Triggerbase, asyncore.dispatcher):
        def __init__(self):

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
            asyncore.dispatcher.__init__(self, r, _map)

        def close(self):
            self.del_channel(_map)
            # self.socket is r, and self.trigger is w, from __init__
            self.socket.close()
            self.trigger.close()

        def pull_trigger(self):
            if __debug__:
                self.logger.debug('notify select %s', pid)
            self.trigger.send('x')

_trigger = _Trigger()

notify_select = _trigger.pull_trigger

def loop():
    timeout = 30.0
    map = _map
    connectors = _connectors
    logger = logging.getLogger('zc.ngi.async.loop')

    while map:
        for f in list(connectors):
            c = connectors.pop(f)
            c.connect()

        try:
            asyncore.poll(timeout, map)
        except:
            logger.exception('loop error')
            raise

_thread = threading.Thread(target=loop)
_thread.setDaemon(True)
_thread.start()
