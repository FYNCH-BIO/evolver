from socketIO_client import SocketIO, BaseNamespace
import time
from threading import Thread
import asyncio
import blink


class EvolverNamespace(BaseNamespace):

    def on_connect(self, *args):
        print('connected cloud')

    def on_disconnect(self, *args):
        print('disconnected cloud')

    def on_reconnect(self, *args):
        print('reconnect cloud')

    def on_command(self, *args):
        print('on_evolver_command', args)
        try:
            to_emit = parse_command(args[0])
            if to_emit:
                self.emit('data', {'data': 'test'})
        except TypeError:
            print('Command payload not valid')


class DpuNamespace(BaseNamespace):

    def on_connect(self, *args):
        print('connected dpu')

    def on_disconnect(self, *args):
        print('disconnected dpu')

    def on_reconnect(self, *args):
        print('reconnect dpu')

    def on_command(self, *args):
        print('on_evolver_command', args)
        try:
            to_emit = parse_command(args[0])
            if to_emit:
                self.emit('data', {'data': 'test'})
        except TypeError:
            print('Command payload not valid')


def start_task_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()


def parse_command(data):
    if not data['cmd']:
        print('No command found')
        return 0

    print(data['cmd'])
    if data['cmd'] == 'start':
        t.start()
        task_loop.call_soon_threadsafe(blink.run)
        return 1
    elif data['cmd'] == 'stop':
        time.sleep(3)
        blink.stop()
        return 0


def start_dpu_thread(socket):
    socket.wait()


if __name__ == '__main__':
    try:
        print('Connecting to Evolver and DPU')
        # Create a new loop
        task_loop = asyncio.new_event_loop()
        # Assign the loop to another thread
        t = Thread(target=start_task_loop, args=(task_loop,))
        # t.daemon = True
        # t.start()

        socketIO_cloud = SocketIO('127.0.0.1', 9000)
        cloud_namespace = socketIO_cloud.define(EvolverNamespace, '/evolver-cloud')

        socketIO_dpu = SocketIO('127.0.0.1', 8081)
        dpu_namespace = socketIO_dpu.define(DpuNamespace, '/evolver-dpu')

        t2 = Thread(target=start_dpu_thread, args=(socketIO_dpu,))

        t2.daemon = True
        t2.start()

        socketIO_cloud.wait()
    except KeyboardInterrupt:
        socketIO_cloud.disconnect()
        socketIO_dpu.disconnect()
