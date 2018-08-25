from socketIO_client import SocketIO, BaseNamespace
import time
from threading import Thread, Event, Semaphore
# import threading
import asyncio
# import blink
import random
import yaml

cloud_namespace = None
dpu_namespace = None
STATE = {'running': False}


# class PausableThread(Thread):
#     def __init__(self, group=None, target=None, name=None, args=(), kwargs={}):
#         self._event = Event()
#         # self.sem = Semaphore()
#         self.paused = False
#         Thread.__init__(self, group=group, target=target, args=args)
#         # if target:
#         #     args = ((lambda: self._event.wait()),) + args
#         # super(PausableThread, self).__init__(group, target, name, args, kwargs)
#
#     def pause(self):
#         # self.paused = True
#         # self.sem.acquire()
#         self._event.clear()
#
#     def resume(self):
#         # self.sem.release()
#         # self.paused = False
#         self._event.set()

class PausableThread(Thread):
    def __init__(self, group=None, target=None, name=None, args=(), kwargs=None, *, daemon=None):
        Thread.__init__(self, group=None, target=target, args=args)
        self.can_run = Event()
        self.thing_done = Event()
        self.thing_done.set()
        self.can_run.set()
        self.paused = False

    def run(self):
        while True:
            self.can_run.wait()
            try:
                self.thing_done.clear()
                self._target(*self._args, **self._kwargs)
            finally:
                self.thing_done.set()

    def pause(self):
        self.paused = True
        self.can_run.clear()
        self.thing_done.wait()

    def resume(self):
        self.paused = False
        self.can_run.set()


class CloudNamespace(BaseNamespace):

    def on_connect(self, *args):
        self.emit('data')
        print('connected cloud')

    def on_disconnect(self, *args):
        print('disconnected cloud')

    def on_reconnect(self, *args):
        print('reconnect cloud')

    def on_experiment(self, data):
        dpu_namespace.emit('experiment', {'id': data['id'], 'alg': data['alg'], 'config': data['config'], 'device': data['device']})
        print('reconnect cloud')

    def on_start(self, data):
        t.resume()
        dpu_namespace.emit('start', {'id': data['id']})
        print("started")

    def on_stop(self, data):
        dpu_namespace.emit('stop', {'id': data['id']})
        print("stopped")

    def on_pause(self, data):
        dpu_namespace.emit('pause', {'id': data['id']})
        print("paused")

    def on_create(self, *args):
        print(args)
        print("created")

    def on_update(self, *args):
        print("updated")


class DpuNamespace(BaseNamespace):

    def on_connect(self, *args):
        print('connected dpu')

    def on_disconnect(self, *args):
        print('disconnected dpu')

    def on_reconnect(self, *args):
        print('reconnect dpu')

    def on_status(self, data):
        # t.resume()
        # t2.resume()
        if data['status'] == 1:
            print('DPU sent start command')
            STATE['running'] = True
            # TODO blink
            task_loop.call_soon_threadsafe(emit_thread, self, data['id'])
        else:
            print('DPU not ready')
        print('status dpu')

    def on_command(self, data):
        print('on_dpu_command', data['cmd'])
        if data['cmd'] == 'result':
            cloud_namespace.emit('result', {'id': data['result']['id'], 'OD': data['result']['OD'],
                                            'temp': data['result']['temp'], 'stir': data['result']['stir']})
            parse_results(data['result'])
        else:
            parse_command(data)


def emit_thread(socket, exp_id):
    print(STATE)
    while STATE['running']:
        t.can_run.wait()
        OD_data = random.random()
        temp_data = random.random()
        stir_data = random.choice([0, 1])
        socket.emit('data', {'id': exp_id, 'data': {'OD': OD_data, 'temp': temp_data, 'stir': stir_data}})
        time.sleep(5)


def start_task_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()


def parse_results(data):
    print("results", data)


def parse_command(data):
    if not data['cmd']:
        print('No command found')
        return 0

    print(data['cmd'])
    if data['cmd'] == 'start':
        t.start()
        # task_loop.call_soon_threadsafe(blink.run)
        return 1
    elif data['cmd'] == 'stop':
        # time.sleep(3)
        # blink.stop()
        STATE['running'] = False
        return 0
    elif data['cmd'] == 'pause':
        STATE['running'] = False
        t.pause()
        return 0


def start_dpu_thread(socket):
    socket.wait()


if __name__ == '__main__':

    FLAGS = lambda: None

    with open('conf.yml', 'r') as ymlfile:
        conf = yaml.load(ymlfile)
        for element in conf:
            setattr(FLAGS, element, conf[element])

    try:
        print('Connecting to Evolver and DPU')
        # Create a new loop
        task_loop = asyncio.new_event_loop()

        t = PausableThread(target=start_task_loop, args=(task_loop,))
        t.start()

        socketIO_cloud = SocketIO(FLAGS.cloud_ip, FLAGS.cloud_port)
        cloud_namespace = socketIO_cloud.define(CloudNamespace, '/evolver-cloud')

        socketIO_dpu = SocketIO(FLAGS.dpu_ip, FLAGS.dpu_port)
        dpu_namespace = socketIO_dpu.define(DpuNamespace, '/evolver-dpu')

        t2 = PausableThread(target=start_dpu_thread, args=(socketIO_dpu,))
        # t2 = Thread(target=start_dpu_thread, args=(socketIO_dpu, e2,))

        t2.daemon = True
        t2.start()

        socketIO_cloud.wait()

    except KeyboardInterrupt:
        socketIO_cloud.disconnect()
        socketIO_dpu.disconnect()
