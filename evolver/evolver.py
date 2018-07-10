from socketIO_client import SocketIO, BaseNamespace
import time
from threading import Thread
import asyncio
import blink
import random
import yaml

cloud_namespace = None
dpu_namespace = None
STATE = {'running': False}


class CloudNamespace(BaseNamespace):

    def on_connect(self, *args):
        self.emit('data')
        print('connected cloud')

    def on_disconnect(self, *args):
        print('disconnected cloud')

    def on_reconnect(self, *args):
        print('reconnect cloud')

    def on_experiment(self, data):
        dpu_namespace.emit('experiment', {'id': data['id'], 'alg': data['alg']})
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

    def on_status(self, data):
        if data['status'] == 1:
            print('DPU sent start command')
            STATE['running'] = True
            # TODO blink
            task_loop.call_soon_threadsafe(emit_thread, self)
        else:
            print('DPU not ready')
        print('status dpu')

    def on_command(self, data):
        print('on_dpu_command', data)
        parse_command(data)


def emit_thread(socket):
    print(STATE)
    while STATE['running']:
        socket.emit('data', {'id': 1, 'data': {'temp': random.random()}})
        time.sleep(1)

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
        # time.sleep(3)
        #blink.stop()
        STATE['running'] = False
        return 0


def start_dpu_thread(socket):
    socket.wait()


if __name__ == '__main__':

    with open('../conf.yml', 'r') as ymlfile:
        conf = yaml.load(ymfile)
        for element in conf:
            setattr(FLAGS, element, conf[element])

    try:
        print('Connecting to Evolver and DPU')
        # Create a new loop
        task_loop = asyncio.new_event_loop()
        # Assign the loop to another thread
        # This is what all evolver commands will run in so we don't block the main thread with a while True loop
        t = Thread(target=start_task_loop, args=(task_loop,))
        t.start()

        socketIO_cloud = SocketIO(FLAGS.cloud_ip, FLAGS.cloud_port)
        cloud_namespace = socketIO_cloud.define(CloudNamespace, '/evolver-cloud')

        socketIO_dpu = SocketIO(FLAGS.dpu_ip, FLAGS.dpu_port)
        dpu_namespace = socketIO_dpu.define(DpuNamespace, '/evolver-dpu')

        t2 = Thread(target=start_dpu_thread, args=(socketIO_dpu,))

        t2.daemon = True
        t2.start()

        socketIO_cloud.wait()
    except KeyboardInterrupt:
        socketIO_cloud.disconnect()
        socketIO_dpu.disconnect()
