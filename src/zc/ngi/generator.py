##############################################################################
#
# Copyright Zope Foundation and Contributors.
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

class handler(object):

    def __init__(self, func):
        self.func = func

    def __call__(self, *args):
        return ConnectionHandler(self.func(*args), args[-1])

    def __get__(self, inst, class_):
        if inst is None:
            return self

        return (lambda connection:
                ConnectionHandler(self.func(inst, connection), connection)
                )

class ConnectionHandler(object):

    def __init__(self, gen, connection):
        try:
            gen.next()
        except StopIteration:
            return

        self.gen = gen
        connection.setHandler(self)

    def handle_input(self, connection, data):
        try:
            self.gen.send(data)
        except StopIteration:
            connection.close()

    def handle_close(self, connection, reason):
        try:
            self.gen.throw(GeneratorExit, GeneratorExit(reason))
        except (GeneratorExit, StopIteration):
            pass

    def handle_exception(self, connection, exception):
        self.gen.throw(exception.__class__, exception)
