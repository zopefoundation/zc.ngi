import logging, os, sys, zc.ngi.async

logging.basicConfig()

class Echo:

    def handle_input(self, connection, data):
        import time; time.sleep(9)
        connection.write(data.upper())

    def handle_close(self, connection, reason):
        print 'closed', reason

    def handle_exception(self, connection, exception):
        print 'oops', exception

def echo_server(connection):
    connection.set_handler(Echo())

def main(args=None):
    if args is None:
        args = sys.argv[1:]
    address, = args
    if ':' in address:
        host, port = address.split(':')
        address = host, int(port)
    listener = zc.ngi.async.main.listener(address, echo_server)
    zc.ngi.async.main.loop()

if __name__ == '__main__':
    sys.exit(main())
