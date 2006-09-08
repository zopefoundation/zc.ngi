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
"""Network Gateway Interface (NGI)

The interfaces are split between "implementation" and "application"
interfaces.  An implementation of the NGI provides IConnection,
IConnector, and IListener. An application provides IConnectionHandler
and one or both of IClientConnectHandler and IServer.

The NGI is an event-based framework in the sense that applications
register handlers that respond to input events.  There are 3 kinds of
handlers:

- Input handlers recieve network input

- Client-connect handlers respond to outbound connection events, and

- Servers respond to incoming connection events.

The interfaces are designed to allow single-threaded applications:

- An implementation of the interfaces is not allowed to make multiple
  simultanious calls to the same application handler.  (Note that this
  requirement does not extend accross multiple implementations.
  Theoretically, different implementations could call handlers at the
  same time.

- All handler calls that are associated with a connection include the
  connection as a parameter,  This allows a single handler object to
  respond to events from multiple connections.

Applications may be multi-threaded.  This means that implementations
must be thread safe.  This means that calls into the implementation
could be made at any time.

$Id$
"""

from zope.interface import Interface, Attribute

class IConnection(Interface):
    """Network connections
  
    Network connections support communication over a network
    connection, or any connection having separate input and output
    channels. 
    """

    def __nonzero__():
        """Return the connection status
        
        True is returned if the connection is open/active and
        False otherwise.
        """

    def setHandler(handler):
        """Set the IConnectionHandler for a connection.

        This methid can only be called in direct response to an
        implementation call to a IConnectionHandler,
        IClientConnectHandler, or IServer
        """

    def write(data):
        """Write output data to a connection.
        
        The write call is non-blocking.
        """

    def close():
        """Close the connection
        """

class IServerConnection(IConnection):

    control = Attribute("An IServerControl")

class IInputHandler(Interface):
    """Objects that can handle connection input-data events

    The methods defined be this interface will never be called
    simultaniously from separate threads, so implementation of the
    methods needn't be concerned with thread safety with respect to
    these methods.
    """

    def handle_input(connection, data):
        """Handle input data from a connection
        
        The data is an 8-bit string.

        Note that there are no promises about blocking.  There data
        isn't necessarily record oriented.  For example, data could,
        in theory be passed one character at a time.  It os up to
        applications to organize data into records, if desired.
        
        """

    def handle_close(connection, reason):
        """Recieve notification that a connection has closed
        
        The reason argument can be converted to a string for logging
        purposes.  It may have data useful for debugging, but this
        is undefined.
        
        Notifications are received when the connection is closed
        externally, for example, when the other side of the
        connection is closed or in case of a network failure.  No
        notification is given when the connection's close method is
        called.      
        """

class IConnector(Interface):
    """Create a connection to a server
    """

    def __call__(address, handler):
        """Try to make a connection to the given address
        
        The handler is an IClientConnectHandler.  The handler
        connected method will be called with an IConnection object
        if and when the connection suceeds or failed_connect method
        will be called if the connection fails.
        """

class IClientConnectHandler(Interface):
    """Recieve notifications of connection results
    """

    def connected(connection):
        """Recieve notification that a connection had been established
        """
        
    def failed_connect(reason):
        """Recieve notificantion that a connection could not be established

        The reason argument can be converted to a string for logging
        purposes.  It may have data useful for debugging, but this
        is undefined.
        """

class IListener(Interface):
    """Listed for incoming connections
    """

    def __call__(address, handler):
        """Listen for incoming connections

        When a connection is recieved, call the handler.

        An IServerControl object is returned.
        """

class IServer(Interface):
    """Handle server connections
    """

    def __call__(connection):
        """Handle a connection from a client
        """

class IServerControl(Interface):
    """Server information and close control
    """

    def connections():
        """return an iterable of the current connections
        """

    def close(handler=None):
        """Close the listener and all of it's connections

        If no handler is passed, the listener and it's connections
        are closed immediately without waiting for any pending input
        to be handled or for pending output to be sent.

        If a handler is passed, the listener will stop accepting new
        connections and existing connections will be left open.  The
        handler will be called when all of the existing connections
        have been closed.
        """
