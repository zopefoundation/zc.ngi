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
from zc.ngi.interfaces import ConnectionFailed
import sys
import threading
import time
import warnings
import zc.ngi
import zc.ngi.adapters

warnings.warn("The blocking module is deprecated.",
              DeprecationWarning, stacklevel=2)

class Timeout(Exception):
    """An operation timed out.
    """

class ConnectionTimeout(Timeout, ConnectionFailed):
    """An attempt to connect timed out.
    """

class RequestConnection(zc.ngi.adapters.Base):

    def __init__(self, connection, connector):
        self.connection = connection
        self.connector = connector

    def close(self):
        self.connector.closed = True
        self.connection.close()
        self.connector.event.set()

    def handle_input(self, connection, data):
        try:
            self.handler.handle_input(self, data)
        except:
            self.connector.exception = sys.exc_info()
            self.connector.event.set()
            raise

    def handle_close(self, connection, reason):
        handle_close = getattr(self.handler, 'handle_close', None)
        if handle_close is not None:
            try:
                handle_close(self, reason)
            except:
                self.connector.exception = sys.exc_info()
                self.connector.event.set()
                raise

        self.connector.closed = True
        self.connector.result = reason
        self.connector.event.set()

    @property
    def handle_exception(self):
        handle = self.handler.handle_exception
        def handle_exception(connection, exception):
            try:
                handle(self, exception)
            except:
                self.connector.exception = sys.exc_info()
                self.connector.event.set()
                raise
        return handle_exception

class RequestConnector:

    exception = closed = connection = result = None

    def __init__(self, handler, event):
        try:
            connected = handler.connected
        except AttributeError:
            if callable(handler):
                connected = handler
            elif getattr(handler, 'handle_input', None) is None:
                raise
            else:
                connected = lambda connection: connection.set_handler(handler)

        self._connected = connected
        self.event = event

    def connected(self, connection):
        self.connection = connection
        try:
            self._connected(RequestConnection(connection, self))
        except:
            self.exception = sys.exc_info()
            self.event.set()
            raise

    def failed_connect(self, reason):
        self.exception = ConnectionFailed(reason)
        self.event.set()

def request(connect, address, connection_handler, timeout=None):
    event = threading.Event()
    connector = RequestConnector(connection_handler, event)
    connect(address, connector)
    event.wait(timeout)

    if connector.exception:
        exception = connector.exception
        del connector.exception
        if isinstance(exception, tuple):
            raise exception[0], exception[1], exception[2]
        else:
            raise exception

    if connector.closed:
        return connector.result

    if connector.connection is None:
        raise ConnectionTimeout
    raise Timeout

def connect(address, connect=None, timeout=None):
    if connect is None:
        connect = zc.ngi.implementation.connect
    return _connector().connect(address, connect, timeout)

class _connector:

    failed = connection = None

    def connect(self, address, connect, timeout):
        event = self.event = threading.Event()
        connect(address, self)
        event.wait(timeout)
        if self.failed is not None:
            raise ConnectionFailed(self.failed)
        if self.connection is not None:
            return self.connection
        raise ConnectionTimeout()

    def connected(self, connection):
        self.connection = connection
        self.event.set()

    def failed_connect(self, reason):
        self.failed = reason
        self.event.set()

def open(connection_or_address, connector=None, timeout=None):
    if connector is None and (hasattr(connection_or_address, 'set_handler')
                              or hasattr(connection_or_address, 'setHandler')
                              ):
        # connection_or_address is a connection
        connection = connection_or_address
    else:
        connection = connect(connection_or_address, connector, timeout)

    outputfile = OutputFile(connection)
    return outputfile, InputFile(connection, outputfile)

class _BaseFile:

    def __init__(self, connection):
        self._connection = connection
        self._position = 0

    def seek(self, offset, whence=0):
        position = self._position
        if whence == 0:
            position = offset
        elif whence == 1:
            position += offset
        elif whence == 2:
            position -= offset
        else:
            raise IOError("Invalid whence argument", whence)
        if position < 0:
            raise IOError("Invalid offset", offset)
        self._position = position

    def tell(self):
        return self._position

    _closed = False
    def _check_open(self):
        if self._closed:
            raise IOError("I/O operation on closed file")

class OutputFile(_BaseFile):

    def invalid_method(*args, **kw):
        raise IOError("Invalid operation on output file")

    read = readline = readlines = invalid_method

    def flush(self):
        self._check_exception()

    def close(self):
        if not self._closed:
            self._connection.close()
        self._closed = True

    def write(self, data):
        self._check_exception()
        self._check_open()
        assert isinstance(data, str)
        self._position += len(data)
        self._connection.write(data)

    def writelines(self, data, timeout=None, nonblocking=False):
        self._check_exception()
        self._check_open()
        if nonblocking:
            self._connection.writelines(iter(data))
            return

        event = threading.Event()
        self._connection.writelines(
            _writelines_iterator(data, self, event.set))
        # wait for iteration to finish
        event.wait(timeout)
        if not event.isSet():
            raise Timeout()

    _exception = None
    def _check_exception(self):
        if self._exception is not None:
            exception = self._exception
            self._exception = None
            raise exception

class _writelines_iterator:

    def __init__(self, base, file, notify):
        self._base = iter(base)
        self._file = file
        self._notify = notify

    def __iter__(self):
        return self

    def next(self):
        try:
            data = self._base.next()
            self._file._position += 1
            return data
        except StopIteration:
            self._notify()
            raise

class InputFile(_BaseFile):

    def __init__(self, connection, outputfile):
        _BaseFile.__init__(self, connection)
        self._condition = threading.Condition()
        self._data = ''
        self._outputfile = outputfile
        self._outputfile._exception = None
        connection.set_handler(self)

    def invalid_method(*args, **kw):
        raise IOError("Invalid operation on output file")

    flush = write = writelines = invalid_method

    def handle_input(self, connection, data):
        condition = self._condition
        condition.acquire()
        self._data += data
        condition.notifyAll()
        condition.release()

    def handle_close(self, connection, reason):
        condition = self._condition
        condition.acquire()
        try:
            self._closed = self._outputfile._closed = True
            condition.notifyAll()
        finally:
            condition.release()

    def handle_exception(self, connection, exception):
        condition = self._condition
        condition.acquire()
        try:
            self._outputfile._exception = exception
            condition.notifyAll()
        finally:
            condition.release()

    def close(self):
        condition = self._condition
        condition.acquire()
        try:
            self._closed = self._outputfile._closed = True
            self._connection.close()
            condition.notifyAll()
        finally:
            condition.release()

    def __iter__(self):
        return self

    def next(self):
        s = self.readline()
        if s:
            return s
        raise StopIteration

    def read(self, size=None, timeout=None):
        deadline = None
        condition = self._condition
        condition.acquire()
        try:
            self._outputfile._check_exception()
            while 1:
                data = self._data
                if size is not None and size <= len(data):
                    data, self._data = data[:size], data[size:]
                    break
                elif self._closed:
                    if data:
                        self._data = ''
                    break

                timeout, deadline = self._wait(timeout, deadline)

            self._position += len(data)
            return data
        finally:
            condition.release()

    def readline(self, size=None, timeout=None):
        deadline = None
        condition = self._condition
        condition.acquire()
        try:
            self._outputfile._check_exception()
            while 1:
                data = self._data
                l = data.find('\n')
                if l >= 0:
                    l += 1
                    if size is not None and size < l:
                        l = size
                    data, self._data = data[:l], data[l:]
                    break
                elif size is not None and size <= len(data):
                    data, self._data = data[:size], data[size:]
                    break
                elif self._closed:
                    if data:
                        self._data = ''
                    break
                timeout, deadline = self._wait(timeout, deadline)

            self._position += len(data)
            return data

        finally:
            condition.release()

    def readlines(self, sizehint=None, timeout=None):
        deadline = None
        condition = self._condition
        condition.acquire()
        try:
            self._outputfile._check_exception()
            while 1:
                data = self._data
                if sizehint is not None and sizehint <= len(data):
                    l = data.rfind('\n')
                    if l >= 0:
                        l += 1
                        data, self._data = data[:l], data[l:]
                        return data.splitlines(True)
                elif self._closed:
                    if data:
                        self._data = ''
                    return data.splitlines()
                timeout, deadline = self._wait(timeout, deadline)
        finally:
            condition.release()

    def _wait(self, timeout, deadline):
        if timeout is not None:
            if deadline is None:
                if timeout <= 0:
                    raise Timeout()
                deadline = time.time() + timeout
            else:
                timeout = deadline - time.time()
                if timeout <= 0:
                    raise Timeout()
            self._condition.wait(timeout)
        else:
            self._condition.wait()

        self._outputfile._check_exception()

        return timeout, deadline

