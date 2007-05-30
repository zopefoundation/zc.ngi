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

Changes
*******

==================
1.0.1 (2007-05-30)
==================

Bugs fixed:

- Server startups sometimes failed with an error like::

    warning: unhandled read event 
    warning: unhandled write event 
    warning: unhandled read event 
    warning: unhandled write event 
    ------ 
    2007-05-30T22:22:43 ERROR zc.ngi.async.server listener error 
    Traceback (most recent call last): 
      File "asyncore.py", line 69, in read 
        obj.handle_read_event() 
      File "asyncore.py", line 385, in handle_read_event 
        self.handle_accept() 
      File "/zc/ngi/async.py", line 325, in handle_accept 
        sock, addr = self.accept() 
    TypeError: unpack non-sequence 
