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
"""NGI connection adapters
"""
import struct
import warnings
import zc.ngi.generator

class Base(object):

    def __init__(self, connection):
        self.connection = connection

    def close(self):
        self.connection.close()

    def write(self, data):
        self.write = self.connection.write
        self.write(data)

    def writelines(self, data):
        self.writelines = self.connection.writelines
        self.writelines(data)

    def set_handler(self, handler):
        self.handler = handler
        try:
            self.connection.set_handler(self)
        except AttributeError:
            self.connection.setHandler(self)
            warnings.warn("setHandler is deprecated. Use set_handler,",
                          DeprecationWarning, stacklevel=2)

    def setHandler(self, handler):
        warnings.warn("setHandler is deprecated. Use set_handler,",
                      DeprecationWarning, stacklevel=2)
        self.set_handler(handler)

    def handle_input(self, connection, data):
        handle_input = self.handler.handle_input
        self.handle_input(connection, data)

    def handle_close(self, connection, reason):
        self.handler.handle_close(connection, reason)

    def handle_exception(self, connection, reason):
        self.handler.handle_exception(connection, reason)

    @classmethod
    def handler(class_, func):
        return zc.ngi.generator.handler(func, class_)

    @property
    def peer_address(self):
        return self.connection.peer_address

    def __nonzero__(self):
        return bool(self.connection)

class Lines(Base):

    input = ''

    def handle_input(self, connection, data):
        self.input += data
        data = self.input.split('\n')
        self.input = data.pop()
        for line in data:
            self.handler.handle_input(self, line)


class Sized(Base):

    want = 4
    got = 0
    getting_size = True

    def set_handler(self, handler):
        self.input = []
        Base.set_handler(self, handler)

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

    def writelines(self, data):
        self.connection.writelines(sized_iter(data))

    def write(self, message):
        if message is None:
            self.connection.write('\xff\xff\xff\xff')
        else:
            self.connection.write(struct.pack(">I", len(message)))
            self.connection.write(message)

def sized_iter(data):
    for message in data:
        if message is None:
            yield '\xff\xff\xff\xff'
        else:
            yield struct.pack(">I", len(message))
            yield message
