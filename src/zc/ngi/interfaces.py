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

class Interface:
    pass
def Attribute(text):
    return text
def implements(*args):
    pass
moduleProvides = implements

try:
    from zope.interface import Interface, Attribute, implements, moduleProvides
except ImportError:
    pass

class IImplementation(Interface):
    """Standard interface for ngi implementations
    """

    def connect(address, handler):
        """Try to make a connection to the given address

        The handler is an ``IClientConnectHandler``.  The handler
        ``connected`` method will be called with an ``IConnection`` object
        if and when the connection succeeds or ``failed_connect`` method
        will be called if the connection fails.

        This method is thread safe. It may be called by any thread at
        any time.
        """

    def listener(address, handler):
        """Listen for incoming TCP connections

        When a connection is received, call the handler.

        An ``IListener`` object is returned.

        This method is thread safe. It may be called by any thread at
        any time.
        """

    def udp(address, message):
        """Send a UDP message

        This method is thread safe. It may be called by any thread at
        any time.
        """

    def udp_listener(address, handler, buffer_size=4096):
        """Listen for incoming UDP messages

        When a message is received, call the handler with the message.

        An ``IUDPListener`` object is returned.

        This method is thread safe. It may be called by any thread at
        any time.
        """

class IConnection(Interface):
    """Network connections

    This is an implementation interface.

    Network connections support communication over a network
    connection, or any connection having separate input and output
    channels.
    """

    def __nonzero__():
        """Return the connection status

        True is returned if the connection is open/active and
        False otherwise.
        """

    def set_handler(handler):
        """Set the ``IConnectionHandler`` for a connection.

        This method may be called multiple times, but it should only
        be called in direct response to an implementation call to a
        ``IConnectionHandler``, ``IClientConnectHandler``, or
        ``IServer``.

        Any failure of a handler call must be caught and logged.  If
        an exception is raised by a call to ``hande_input`` or
        ``handle_exception``, the connection must be closed by the
        implementation.
        """

    def write(data):
        """Output a string to the connection.

        The write call is non-blocking.

        This method is thread safe. It may be called by any thread at
        any time.
        """

    def writelines(data):
        """Output an iterable of strings to the connection.

        The ``writelines`` call is non-blocking. Note, that the data may
        not have been consumed when the method returns.

        This method is thread safe. It may be called by any thread at
        any time.
        """

    def close():
        """Close the connection

        This method is thread safe. It may be called by any thread at
        any time.
        """

    peer_address = Attribute(
        """The peer address

        For socket-based connectionss, this is the result of calling
        getpeername on the socket.

        This is primarily interesting for servers that want to vary
        behavior depending on where clients connect from.
        """)

class IServerConnection(IConnection):
    """Server connection

    This is an implementation interface.
    """

    control = Attribute("An IListener")

class IConnectionHandler(Interface):
    """Application objects that can handle connection input-data events

    This is an application interface.

    The methods defined be this interface will never be called
    simultaneously from separate threads, so implementation of the
    methods needn't be concerned with thread safety with respect to
    these methods.
    """

    def handle_input(connection, data):
        """Handle input data from a connection

        The data is an 8-bit string.

        Note that there are no promises about data organization.  The
        data isn't necessarily record oriented.  For example, data
        could, in theory be passed one character at a time.  It is up
        to applications to organize data into records, if desired.
        """

    def handle_close(connection, reason):
        """Receive notification that a connection has closed

        The reason argument can be converted to a string for logging
        purposes.  It may have data useful for debugging, but this
        is undefined.

        Notifications are received when the connection is closed
        externally, for example, when the other side of the
        connection is closed or in case of a network failure.  No
        notification is given when the connection's close method is
        called.
        """

    def handle_exception(connection, exception):
        """Recieve a report of an exception encountered by a connection

        This method is used to recieve exceptions from an NGI
        implementation.  This will only be due to an error
        encounted processing data passed to the connection
        ``writelines`` methods.
        """

class IClientConnectHandler(Interface):
    """Receive notifications of connection results

    This is an application interface.
    """

    def connected(connection):
        """Receive notification that a connection had been established
        """

    def failed_connect(reason):
        """Receive notification that a connection could not be established

        The reason argument can be converted to a string for logging
        purposes.  It may have data useful for debugging, but this
        is undefined.
        """

class IServer(Interface):
    """Handle server connections

    This is an application interface.

    A server is just a callable that takes a connection and set's it's
    handler.
    """

    def __call__(connection):
        """Handle a connection from a client
        """


class IUDPHandler(Interface):
    """Handle udp messages

    This is an application interface.

    A UDP handler is a callable that takes a client address and an
    8-bit string message.
    """

    def __call__(addr, data):
        """Handle a connection from a client
        """


class IListener(Interface):
    """Listener information and close control

    This is an implementation interface.
    """

    address = Attribute("The address the listener is listening on.")

    def connections():
        """return an iterable of the current connections
        """

    def close(handler=None):
        """Close the listener and all of its connections

        If no handler is passed, the listener and its connections
        are closed immediately without waiting for any pending input
        to be handled or for pending output to be sent.

        If a handler is passed, the listener will stop accepting new
        connections and existing connections will be left open.  The
        handler will be called when all of the existing connections
        have been closed.
        """

class IUDPListener(Interface):
    """UDP Listener close control

    This is an implementation interface.
    """

    def close():
        """Close the listener
        """

class ConnectionFailed(Exception):
    """A Connection attempt failed
    """

class Timeout(Exception):
    """Something took too long
    """
