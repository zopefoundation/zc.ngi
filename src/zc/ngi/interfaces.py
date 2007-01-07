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

- Input handlers receive network input

- Client-connect handlers respond to outbound connection events, and

- Servers respond to incoming connection events.

The interfaces are designed to allow single-threaded applications:

- An implementation of the interfaces is not allowed to make multiple
  simultaneous calls to the same application handler.  (Note that this
  requirement does not extend across multiple implementations.
  Theoretically, different implementations could call handlers at the
  same time.)

- All handler calls that are associated with a connection include the
  connection as a parameter,  This allows a single handler object to
  respond to events from multiple connections.

Applications may be multi-threaded.  This means that implementations
must be thread safe.  This means that, unless otherwise stated, calls
into the implementation could be made at any time.

$Id$
"""

from zope.interface import Interface, Attribute

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

    def setHandler(handler):
        """Set the IConnectionHandler for a connection.

        This method can only be called in direct response to an
        implementation call to a IConnectionHandler,
        IClientConnectHandler, or IServer
        """

    def write(data):
        """Output a string to the connection.
        
        The write call is non-blocking.
        """

    def writelines(data):
        """Output an iterable of strings to the connection.
        
        The writelines call is non-blocking. Note, that the data may
        not have been consumed when the method returns.        
        """

    def close():
        """Close the connection
        """

class IServerConnection(IConnection):
    """Server connection
    
    This is an implementation interface.
    """
    
    control = Attribute("An IServerControl")

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

        Note that there are no promises about blocking.  The data
        isn't necessarily record oriented.  For example, data could,
        in theory be passed one character at a time.  It is up to
        applications to organize data into records, if desired.
        
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
        implementation.  Typically, this will be due to an error
        encounted processing data passed to the connection write or
        writelines methods.
        """

class IConnector(Interface):
    """Create a connection to a server
    
    This is an implementation interface.
    """

    def __call__(address, handler):
        """Try to make a connection to the given address
        
        The handler is an IClientConnectHandler.  The handler
        connected method will be called with an IConnection object
        if and when the connection succeeds or failed_connect method
        will be called if the connection fails.
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

class IListener(Interface):
    """Listed for incoming connections
    
    This is an implementation interface.
    """

    def __call__(address, handler):
        """Listen for incoming connections

        When a connection is received, call the handler.

        An IServerControl object is returned.
        """

class IServer(Interface):
    """Handle server connections

    This is an application interface.
    """

    def __call__(connection):
        """Handle a connection from a client
        """

class IServerControl(Interface):
    """Server information and close control
    
    This is an implementation interface.
    """

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

class IBlocking(Interface):
    """Top-level blocking interface provided by the blocking module
    """

    def connect(address, connector, timeout=None):
        """Connect to the given address using the given connector

        A timout value may be given as a floating point number of
        seconds.

        If connection suceeds, an IConnection is returned, otherwise
        an exception is raised.
        """

    def open(connection_or_address, connector=None, timeout=None):
        """Get output and input files for a connection or address

        The first argument is either a connection or an address.
        If (and only if) it is an address, then a connector must be
        provided as the second argument and a connection is gotten by
        calling the connect function with the given address,
        connector, and timeout.

        A pair of file-like objects is returned. The first is an
        output file-like object, an IBlockingOutput, for sending
        output to the connection.  The second file-like object is an
        input file-like object, an IBlockingInput, for reading data
        from the connection.
        """

class IBlockingPositionable(Interface):
    """File-like objects with file positions.

    To mimic file objects, working seek and tell methods are provided
    that report and manipulate pseudo file positions.  The file
    position starts at zero and is advanced by reading or writing
    data. It can be adjusted (pointlessly) by the seek method.
    """

    def tell():
        """Return the current file position.
        """

    def seek(offset, whence=0):
        """Reset the file position

        If whence is 0, then the file position is set to the offset.

        If whence is 1, the position is increased by the offset.

        If whence is 2, the position is decreased by the offset.

        An exception is raised if the position is set to a negative
        value. 
        """

    def close():
        """Close the connection.
        """

class IBlockingOutput(IBlockingPositionable):
    """A file-like object for sending output to a connection.
    """

    def flush():
        """Do nothing.
        """

    def write(data):
        """Write a string to the connection.

        The function will return immediately.  The data may be queued.
        """

    def writelines(iterable, timeout=0, nonblocking=False):
        """Write an iterable of strings to the connection.

        By default, the call will block until the data from the
        iterable has been consumed.  If a true value is passed to the
        non-blocking keyword argument, then the function will return
        immediately. The iterable will be consumed at some later time.

        In (the default) blocking mode, a timeout may be provided to
        limit the time that the call will block.  If the timeout
        expires, a zc.ngi.blocking.Timeout excation will be raised.
        """

class IBlockingInput(IBlockingPositionable):
    """A file-like object for reading input from a connection.
    """

    def read(size=None, timeout=None):
        """Read data

        If a size is specified, then that many characters are read,
        blocking of necessary.  If no size is specified (or if size is
        None), then all remaining input data are read.

        A timeout may be specified as a floating point number of
        seconds to wait.  A zc.ngi.blocking.Timeout exception will be
        raised if the data cannot be read in the number of seconds given.
        """

    def readline(size=None, timeout=None):
        """Read a line of data

        If a size is specified, then the lesser of that many
        characters or a single line of data are read, blocking of
        necessary.  If no size is specified (or if size is None), then
        a single line are read.

        A timeout may be specified as a floating point number of
        seconds to wait.  A zc.ngi.blocking.Timeout exception will be
        raised if the data cannot be read in the number of seconds given.
        """

    def readlines(sizehint=None, timeout=None):
        """Read multiple lines of data

        If a sizehint is specified, then one or more lines of data are
        returned whose total length is less than or equal to the size
        hint, blocking if necessary. If no sizehint is specified (or
        if sizehint is None), then the remainder of input, split into
        lines, is returned.

        A timeout may be specified as a floating point number of
        seconds to wait.  A zc.ngi.blocking.Timeout exception will be
        raised if the data cannot be read in the number of seconds given.
        """

        

    def __iter__():
        """Return the input object
        """

    def next():
        """Return a line of input

        Raises StopIteration if there is no more input.
        """
