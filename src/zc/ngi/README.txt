=========================
Network Gateway Interface
=========================

Network programs are typically difficult to test because they require
setting up network connections, clientts, and servers.  In addition,
application code gets mixed up with networking code.

The Network Gateway Interface (NGI) seeks to improve this situation by
separating application code from network code.  This allows
application and network code to be tested indepenndly and provides
greater separation of concerns.

There are several interfaces defined by the NGI:

IConnection
    Network connection implementation.  This is the core interface that
    applications interact with,

IConnectionHandler
    Application component that handles network input.  

IConnector
    Create IConnection objects by making outgoing connections.

IClientConnectHandler
    Application callback that handles successful ot failed outgoing
    connections.

IListener
    Listed for incoming connections.

IServer
    Callback to handle incoming connections.

The interfaces are split between "implementation" and "application"
interfaces.  An implementation of the NGI provides IConnection,
IConnector, and IListener. An application provides IConnectionHandler
and one or both of IClientConnectHandler and IServer.

For more information, see interfaces.py.

Testing Implementation
======================

These interface can have a number of implementations.  The simplest
implementation is the testing implementation, which is used to test
application code.

    >>> import zc.ngi.testing

The testing module provides IConnection, IConnector, and IListener
implentations. We'll use this below to illustrate how application code
is written.

Implementing Network Clients
============================

Network clients make connections to and then use these connections to
communicate with servers.  To do so, a client must be provided with an
IConnector implemantation.  How this happens is outside the scope of
the NGI.  An IConnector implementation could, for example, be provided
via the Zope component architecture, or via pkg_resources entry
points.

Let's create a simple client that calls an echo server and verifies
that the server properly echoes data sent do it.

    >>> class EchoClient:
    ...
    ...     def __init__(self, connector):
    ...         self.connector = connector
    ...
    ...     def check(self, addr, strings):
    ...         self.strings = strings
    ...         self.connector(addr, self)
    ...
    ...     def connected(self, connection):
    ...         for s in self.strings:
    ...             connection.write(s + '\n')
    ...         self.input = ''
    ...         connection.setHandler(self)
    ...
    ...     def failed_connect(self, reason):
    ...         print 'failed connect:', reason
    ...
    ...     def handle_input(self, connection, data):
    ...         print 'got input:', repr(data)
    ...         self.input += data
    ...         while '\n' in self.input:
    ...             data, self.input = self.input.split('\n', 1)
    ...             if self.strings:
    ...                expected = self.strings.pop(0)
    ...                if data == expected:
    ...                    print 'matched:', data
    ...                else:
    ...                    print 'unmatched:', data
    ...                if not self.strings:
    ...                    connection.close()
    ...             else:
    ...                print 'Unexpected input', data
    ...
    ...     def handle_close(self, connection, reason):
    ...         print 'closed:', reason
    ...         if self.strings:
    ...             print 'closed prematurely'    


The client impements the IClientConnectHandler and IInputHandler
interfaces.  More complex clients might implement these interfacs with
separate classes.

We'll instantiate our client using the testing connector:

    >>> client = EchoClient(zc.ngi.testing.connector)

Now we'll try to check a non-existent server:

    >>> client.check(('localhost', 42), ['hello', 'world', 'how are you?'])
    failed connect: no such server

Our client simply prints a message (and gives up) if a connection
fails. More complex applications might retry, waiting between attemps,
and so on.

The testing connector always fails unless given a test connection
ahead of time.  We'll create a testing connection and register it so a
connection can suceed:

    >>> connection = zc.ngi.testing.Connection()
    >>> zc.ngi.testing.connectable(('localhost', 42), connection)

We can register multiple connections with the same address:

    >>> connection2 = zc.ngi.testing.Connection()
    >>> zc.ngi.testing.connectable(('localhost', 42), connection2)

The connections will be used in order.

Now, our client should be able to connect to the first connection we
created:

    >>> client.check(('localhost', 42), ['hello', 'world', 'how are you?'])
    -> 'hello\n'
    -> 'world\n'
    -> 'how are you?\n'

The test connection echoes data written to it, preceeded by "-> ".

Active connections are true:

    >>> bool(connection2)
    True

Test connections provide mehods generating test input and flow closing
connections.  We can use these to simulate network events.  Let's
generate some input for our client:

    >>> connection.test_input('hello')
    got input: 'hello'

    >>> connection.test_input('\nbob\n')
    got input: '\nbob\n'
    matched: hello
    unmatched: bob

    >>> connection.test_close('done')
    closed: done
    closed prematurely

    >>> client.check(('localhost', 42), ['hello'])
    -> 'hello\n'

    >>> connection2.test_input('hello\n')
    got input: 'hello\n'
    matched: hello
    -> CLOSE

    >>> bool(connection2)
    False
    

Implementing network servers
============================

Implementing network servers is very similar to implementing clients,
except that a listener, rather than a connector is used.  Let's
implement a simple echo server:


    >>> class EchoServer:
    ...
    ...     def __init__(self, connection):
    ...         print 'server connected'
    ...         self.input = ''
    ...         connection.setHandler(self)
    ...
    ...     def handle_input(self, connection, data):
    ...         print 'server got input:', repr(data)
    ...         self.input += data
    ...         if '\n' in self.input:
    ...             data, self.input = self.input.split('\n', 1)
    ...             connection.write(data + '\n')
    ...             if data == 'Q':
    ...                 connection.close()
    ...
    ...     def handle_close(self, connection, reason):
    ...         print 'server closed:', reason

Out EchoServer *class* provides IServer and implement IInputHandler.

To use a server, we need a listener.  We'll use the use the testing
listener:

    >>> listener = zc.ngi.testing.listener(EchoServer)

To simulate a client connection, we create a testing connection and
call the listener's connect method:

    >>> connection = zc.ngi.testing.Connection()
    >>> listener.connect(connection)
    server connected

    >>> connection.test_input('hello\n')
    server got input: 'hello\n'
    -> 'hello\n'

    >>> connection.test_close('done')
    server closed: done

    >>> connection = zc.ngi.testing.Connection()
    >>> listener.connect(connection)
    server connected

    >>> connection.test_input('hello\n')
    server got input: 'hello\n'
    -> 'hello\n'

    >>> connection.test_input('Q\n')
    server got input: 'Q\n'
    -> 'Q\n'
    -> CLOSE

Note that it is an error to write to a closed connection:

    >>> connection.write('Hello')
    Traceback (most recent call last):
    ...
    TypeError: Connection closed


Server Control
--------------

The object returned from a listener is an IServerControl.  It provides
access to the active connections:

    >>> list(listener.connections())
    []

    >>> connection = zc.ngi.testing.Connection()
    >>> listener.connect(connection)
    server connected
   
    >>> list(listener.connections()) == [connection]
    True

    >>> connection2 = zc.ngi.testing.Connection()
    >>> listener.connect(connection2)
    server connected

    >>> len(list(listener.connections()))
    2
    >>> connection in list(listener.connections())
    True
    >>> connection2 in list(listener.connections())
    True

Server connections have a control attribute that is the connections
server control:

    >>> connection.control is listener
    True

Server control objects provide a close method that allows a server to
be shut down.  If the close method is called without arguments, then
then all server connections are closed immediately and no more
connections are accepted:

    >>> listener.close()
    server closed: stopped
    server closed: stopped

    >>> connection = zc.ngi.testing.Connection()
    >>> listener.connect(connection)
    Traceback (most recent call last):
    ...
    TypeError: Listener closed

If a handler function is passed, then connections aren't closed
immediately:

    >>> listener = zc.ngi.testing.listener(EchoServer)
    >>> connection = zc.ngi.testing.Connection()
    >>> listener.connect(connection)
    server connected
    >>> connection2 = zc.ngi.testing.Connection()
    >>> listener.connect(connection2)
    server connected

    >>> def handler(control):
    ...     if control is listener:
    ...        print 'All connections closed'

    >>> listener.close(handler)

But no more connections are accepted:

    >>> connection3 = zc.ngi.testing.Connection()
    >>> listener.connect(connection3)
    Traceback (most recent call last):
    ...
    TypeError: Listener closed
    
And the handler will be called when all of the listener's connections
are closed:

    >>> connection.close()
    -> CLOSE
    >>> connection2.close()
    -> CLOSE
    All connections closed

Long output
===========

Test requests output data written to them.  If output exceeds 50
characters in length, it is wrapped by simply breakng the repr into 
50-characters parts:

    >>> connection = zc.ngi.testing.Connection()
    >>> connection.write('hello ' * 50)
    -> 'hello hello hello hello hello hello hello hello h
    .> ello hello hello hello hello hello hello hello hel
    .> lo hello hello hello hello hello hello hello hello
    .>  hello hello hello hello hello hello hello hello h
    .> ello hello hello hello hello hello hello hello hel
    .> lo hello hello hello hello hello hello hello hello
    .>  '

END_OF_DATA
===========

Closing a connection closes it immediately, without sending any
pending data.  An alternate way to close a connection is to write
zc.ngi.END_OF_DATA. The connection will be automatically closed when
zc.ngi.END_OF_DATA is encountered in the output stream.

    >>> connection.write(zc.ngi.END_OF_DATA)
    -> CLOSE

    >>> connection.write('Hello')
    Traceback (most recent call last):
    ...
    TypeError: Connection closed

Peer connectors
===============

It is sometimes useful to connect a client handler and a server
handler.  The zc.ngi.testing.peer function can be used to create a 
connection to a peer handler. To illustrate, we'll set up an echo
client that connects to our echo server:

    >>> client = EchoClient(zc.ngi.testing.peer(('localhost', 42), EchoServer))
    >>> client.check(('localhost', 42), ['hello', 'world', 'how are you?'])
    server connected
    server got input: 'hello\n'
    server got input: 'world\n'
    server got input: 'how are you?\n'
    got input: 'hello\nworld\nhow are you?\n'
    matched: hello
    matched: world
    matched: how are you?
    server closed: closed
