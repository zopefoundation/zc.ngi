*************************
Network Gateway Interface
*************************

Network programs are typically difficult to test because they require
setting up network connections, clients, and servers.  In addition,
application code gets mixed up with networking code.

The Network Gateway Interface (NGI) seeks to improve this situation by
separating application code from network code.  This allows
application and network code to be tested independently and provides
greater separation of concerns.

.. contents::

