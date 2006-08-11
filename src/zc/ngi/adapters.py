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


    
