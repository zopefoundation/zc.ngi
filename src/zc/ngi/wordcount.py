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
"""Sample NGI server and client

This file provides a sample NGI server and client that counts words.

$Id$
"""

import errno
import logging
import os
import random
import socket
import sys
import threading
import time

import zc.ngi
import zc.ngi.async
import zc.ngi.message

_lock = threading.Lock()
_lock.acquire()

logger = logging.getLogger('zc.ngi.wordcount')

class Server:

    def __init__(self, connection):
        if __debug__:
            logger.debug("Server(%r)", connection)
        self.input = ''
        connection.set_handler(self)

    def handle_input(self, connection, data):
        if __debug__:
            logger.debug("server handle_input(%r, %r)", connection, data)
        self.input += data
        while '\0' in self.input:
            data, self.input = self.input.split('\0', 1)
            if data == 'Q':
                connection.write('Q\n')
                connection.close()
                connection.control.close()
                return
            elif data == 'C':
                connection.close()
                return
            elif data == 'E':
                raise ValueError(data)
            else:
                cc = len(data)
                lc = len(data.split('\n'))-1
                wc = len(data.split())
            connection.write("%s %s %s\n" % (lc, wc, cc))

    def handle_close(self, connection, reason):
        if __debug__:
            logger.debug("server handle_close(%r, %r)", connection, reason)

def serve():
    port, level = sys.argv[1:]
    logfile = open('server.log', 'w')
    handler = logging.StreamHandler(logfile)
    logging.getLogger().addHandler(handler)
    logger.setLevel(int(level))
    logger.addHandler(logging.StreamHandler())
    logger.info('serving')
    zc.ngi.async.listener(('localhost', int(port)), Server)
    zc.ngi.async.wait(11)
    logging.getLogger().removeHandler(handler)
    handler.close()

def get_port():
    """Return a port that is not in use.

    Checks if a port is in use by trying to connect to it.  Assumes it
    is not in use if connect raises an exception.

    Raises RuntimeError after 10 tries.
    """
    for i in range(10):
        port = random.randrange(20000, 30000)
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            try:
                s.connect(('localhost', port))
            except socket.error:
                # Perhaps we should check value of error too.
                return port
        finally:
            s.close()
    raise RuntimeError("Can't find port")

def wait(addr, up=True):
    for i in range(120):
        time.sleep(0.25)
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect(addr)
            s.close()
            if up:
                break
        except socket.error, e:
            if e[0] not in (errno.ECONNREFUSED, errno.ECONNRESET):
                raise
            s.close()
            if not up:
                break
    else:
        if up:
            print "Could not connect"
        else:
            print "Server still accepting connections"

def start_server_process(loglevel=None):
    """Start a server in a subprocess and return the port used
    """
    port = get_port()
    env = dict(
        os.environ,
        PYTHONPATH=os.pathsep.join(sys.path),
        )
    if loglevel is None:
        loglevel = logger.getEffectiveLevel()
    os.spawnle(os.P_NOWAIT, sys.executable, sys.executable, __file__,
               str(port), str(loglevel),
               env)
    addr = 'localhost', port
    wait(addr)
    return port

def stop_server_process(connect, addr):
    zc.ngi.message.message(connect, addr, 'Q\0')
    wait(addr, up=False)
    log = open('server.log').read()
    os.remove('server.log')
    print log,

sample_docs = [
"""Hello world
""",
"""I give my pledge as an earthling
to save and faithfully to defend from waste
the natural resources of my planet
its soils, minerals, forests, waters and wildlife.
""",
"""On my honor, I will do my best
to do my duty to God and my country
and to obey the Scout Law
to always help others
to keep myself physically strong, mentally awake, and morally straight.
""",
"""What we have here, is a failure to communicate.
""",
]

class Client:

    def __init__(self, docs=sample_docs, notify=None):
        self.docs = list(docs)
        self.notify = notify
        self.input = ''

    def connected(self, connection):
        if __debug__:
            logger.debug("connected(%r)", connection)
        connection.write(self.docs[0]+'\0')
        connection.set_handler(self)

    def failed_connect(self, reason):
        print 'Failed to connect:', reason
        self.notify()

    def handle_input(self, connection, data):
        if __debug__:
            logger.debug("client handle_input(%r, %r)", connection, data)
        self.input += data
        if '\n' in self.input:
            data, self.input = self.input.split('\n', 1)
            doc = self.docs.pop(0)
            cc = len(doc)
            lc = len(doc.split('\n'))-1
            wc = len(doc.split())
            expected = "%s %s %s" % (lc, wc, cc)
            if data != expected:
                print '%r != %r' % (data, expected)
            if self.docs:
                connection.write(self.docs[0]+'\0')
            else:
                connection.close()
                if self.notify is not None:
                    self.notify()

    def handle_close(self, connection, reason):
        if __debug__:
            logger.debug("client handle_close(%r, %r)", connection, reason)
        if self.docs:
            print 'unexpected close', reason

def client_thread(connect, addr):
    logger.info('client started for %s', addr)
    lock = threading.Lock()
    lock.acquire()
    client = Client(notify=lock.release)
    connect(addr, client)
    logger.info('client waiting')
    lock.acquire() # wait till done
    logger.info('client done')

if __name__ == '__main__':
    serve()
