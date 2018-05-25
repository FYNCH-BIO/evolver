from socketIO_client import SocketIO, BaseNamespace


class EvolverNamespace(BaseNamespace):
    def on_connect(self, *args):
        print('connected client')

    def on_disconnect(self, *args):
        print('disconnect')

    def on_reconnect(self, *args):
        print('reconnect')

    def on_command(self, *args):
        print('on_evolver_command', args)
        try:
            parse_command(args[0])
            self.emit('data', {'data': 'test'})
        except TypeError:
            print('Command payload not valid')


def parse_command(data):
    if not data['cmd']:
        print('No command found')
        return
    print(data['cmd'])


if __name__ == '__main__':
    socketIO = SocketIO('127.0.0.1', 8080)
    evolver_namespace = socketIO.define(EvolverNamespace, '/evolver')
    socketIO.wait()
