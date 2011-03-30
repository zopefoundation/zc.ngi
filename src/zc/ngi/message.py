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
"""Sample client that sends a single message and waits for a reply
"""

import threading
import warnings

class CouldNotConnect(Exception):
    """Could not connect to a server
    """

class UnexpectedResponse(Exception):
    """Got an unexpected response from a server
    """

class Message:

    def __init__(self, message, expected, notify):
        self.message = message
        self.expected = expected
        self.notify = notify
        self.input = ''

    def connected(self, connection):
        connection.set_handler(self)
        connection.write(self.message)

    def failed_connect(self, reason):
        self.notify(None, reason)

    def handle_input(self, connection, data):
        self.input += data
        if self.expected is not None and self.expected(self.input):
            connection.close()
            self.handle_close(connection)

    def handle_close(self, connection, reason=None):
        self.notify(self.input, reason)


def message(connect, addr, message, expected=None):
    result = []
    lock = threading.Lock()
    lock.acquire()
    def notify(*args):
        if result:
            return # already notified
        result.extend(args)
        lock.release()
    connect(addr, Message(message, expected, notify))
    lock.acquire()
    data, reason = result

    if reason is None:
        return data

    if data is None:
        raise CouldNotConnect(reason)

    if expected is not None and not expected(data):
        raise UnexpectedResponse(data, reason)

    return data
