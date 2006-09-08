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
"""NGI connection adapters

$Id$
"""
import struct

class Lines:

    def __init__(self, connection):
        self.connection = connection
        self.close = connection.close
        self.write = connection.write

    def setHandler(self, handler):
        self.handler = handler
        self.input = ''
        self.connection.setHandler(self)

    def handle_input(self, connection, data):
        self.input += data
        data = self.input.split('\n')
        self.input = data.pop()
        for line in data:
            self.handler.handle_input(self, line)

    def handle_close(self, connection, reason):
        self.handler.handle_close(self, reason)


class Sized:

    def __init__(self, connection):
        self.connection = connection
        self.close = connection.close

    def setHandler(self, handler):
        self.handler = handler
        self.input = []
        self.want = 4
        self.got = 0
        self.getting_size = True
        self.connection.setHandler(self)

    def handle_input(self, connection, data):
        self.got += len(data)
        self.input.append(data)
        while self.got >= self.want:
            extra = self.got - self.want
            if extra == 0:
                collected = ''.join(self.input)
                self.input = []
            else:
                input = self.input
                self.input = [data[-extra:]]
                input[-1] = input[-1][:-extra]
                collected = ''.join(input)

            self.got = extra

            if self.getting_size:
                # we were recieving the message size
                assert self.want == 4
                if collected == '\xff\xff\xff\xff':
                    # NULL message. Ignore
                    continue
                self.want = struct.unpack(">I", collected)[0]
                self.getting_size = False
            else:
                self.want = 4
                self.getting_size = True
                self.handler.handle_input(self, collected)

    def handle_close(self, connection, reason):
        self.handler.handle_close(self, reason)

    def write(self, message):
        if message is None:
            self.connection.write('\xff\xff\xff\xff')
        else:
            self.connection.write(struct.pack(">I", len(message)))
            self.connection.write(message)
    
