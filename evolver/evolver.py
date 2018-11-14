from socketIO_client import SocketIO, BaseNamespace
import socket
import socketio
import time
import yaml
import serial
import asyncio
import numpy as np
from multi_server import MultiServer
from threading import Thread, Event, Semaphore

dpu_namespace = None
evolver_ip = None

SERIAL = serial.Serial(port="/dev/ttyAMA0", baudrate = 9600, timeout = 2)
SERIAL.flushInput()
SERIAL.close()

DEFAULT_PARAMS = {"OD":["we", "turb", "all"], "temp":["xr", "temp","all"], "stir": ["zv", "stir", "all"], "pump": ["st", "pump", "all"]}
DEFAULT_CONFIG = {}
PARAM = {}
DATA = {}
#CONFIG = {'OD':[2125] * 16, 'temp':[300] * 16, 'stir':[10]*16, 'pump':['t','1111111111','5','0','0','0','0','0','0','0','0','0','0','0','0','0','0','0']}
CONFIG = {}

ENDING_SEND = '!'
ENDING_RETURN = 'end'

global sio
sio = socketio.AsyncServer()

@sio.on('connect', namespace = '/dpu-evolver')
async def on_connect(sid, environ):
    print('Connected dpu')

@sio.on('start', namespace = '/dpu-evolver')
async def on_start(sid, data):
    print('starting to send data')
    if data['evolver_ip'] == evolver_ip:
        print('Starting experiment')
        if t.paused:
            t.resume()
        task_loop.call_soon_threadsafe(emit_thread, dpu_namespace, data['exp_id'])

@sio.on('stop', namespace = '/dpu-evolver')
async def on_stop(sid, data):
    if data['evolver_ip'] == evolver_ip:
        print('stop')
        t.pause()

@sio.on('define', namespace = '/dpu-evolver')
async def on_define(sid, data):
    print('finally defining')
    if data['evolver_ip'] == evolver_ip:
        print('defining params')
        define_parameters(data['params'])
        define_default_config(data['config'])

@sio.on('disconnect', namespace = '/dpu-evolver')
async def on_disconnect(sid):
    print('finally disconnected')

@sio.on('command', namespace = '/dpu-evolver')
async def on_command(sid, data):
    if data['evolver_ip'] == evolver_ip:
        param = data.get('param')
        message = data.get('message')
        vials = data.get('vials')
        values = data.get('values')
        if message:
            CONFIG[param] = message
        else:
            parse_set(param, vials, values)
        push_arduino()
        SERIAL.close()
        CONFIG.clear()

def parse_set(param, vials, values):
    arduino_message = []
    vials = list(map(int,vials.split(',')))
    if param == 'pump':
        arduino_message = get_turbidostat_command(vials, values)
    else:
        arduino_message = values.split(',')
    CONFIG[param] = arduino_message

def get_turbidostat_command(vial_nums, num_secs):
    num_secs = float(num_secs)
    control = np.power(2, range(0,32), dtype='int64')
    print(control)
    empty_vals = [0] * 15
    print(vial_nums)
    pumps_control = 0
    for vial_num in vial_nums:
        pumps_control += control[vial_num]
    pumps_binary = "{0:b}".format(pumps_control)

    while len(pumps_binary) < 16:
        pumps_binary = '0' + pumps_binary
    pump_cmd = ["t", pumps_binary, '{:.2f}'.format(num_secs)] + empty_vals

    return pump_cmd
        

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
        self.thing_done.set()


class DpuNamespace(BaseNamespace):

    def on_start(self, data):
        print('received a start command')

    def on_connect(self, *args):
        print('connected dpu')
        self.emit('ip', {'ip': evolver_ip}) 

    def on_disconnect(self, *args):
        print('disconnected dpu')

    def on_reconnect(self, *args):
        print('reconnect dpu')



def emit_thread(dpu_socket, exp_id):
    while not t.paused:
        t.can_run.wait()
        global CONFIG
        global DEFAULT_CONFIG
        CONFIG = DEFAULT_CONFIG.copy()
        print('default config')
        print(CONFIG)
        ping_arduino()
        dpu_socket.emit('data', {'id': exp_id, 'data': {'OD': DATA['OD'], 'temp': DATA['temp']}})        
        t.thing_done.set()
        CONFIG.clear()
        time.sleep(5)

def start_task_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()        

def start_dpu_thread(socket):
    socket.wait()

def config_to_arduino(key, header, ending, method):
    print('config to arduino...')
    global CONFIG
    global DEFUALT_CONFIG
    if not CONFIG:
        CONFIG = DEFAULT_CONFIG.copy()
    if 'temp' in CONFIG:
        DEFAULT_CONFIG['temp'] = CONFIG['temp']
    myList = CONFIG.get(key)
    SERIAL.open()
    SERIAL.flushInput()
    output = ''
    if method == 'all' and myList is not None:
        myString = ','.join(map(str,myList))
        output = header + myString + ', ' + ending
        print(output)
        SERIAL.write(bytes(output, 'UTF-8'))

    if method == 'indiv' and myList is not None:
        for x in myList.split(','):
            output = header + x + ending
            SERIAL.write(bytes(output,'UTF-8'))

def data_from_arduino(key, header, ending):
    try:
        received = SERIAL.readline().decode('utf-8')
        if received[0:4] == header and received[-3:] == ending:
            dataList = [int(s) for s in received[4:-4].split(',')]
            DATA[key] = dataList
        else:
            DATA[key] = 'NaN'
    except ValueError:
        DATA[key] = 'NaN'
    SERIAL.close()


def ping_arduino():
    global CONFIG
    print('this is my config now')
    print(CONFIG)
    for key, value in CONFIG.items():
        print('getting ' + key)
        config_to_arduino(key, PARAM[key][0], ENDING_SEND, PARAM[key][2])
        data_from_arduino(key, PARAM[key][1], ENDING_RETURN)

def push_arduino():
    global CONFIG
    for key, value in CONFIG.items():
        config_to_arduino(key, PARAM[key][0], ENDING_SEND, PARAM[key][2])
    CONFIG.clear()

def define_parameters(param_json):
    PARAM.clear()
    PARAM.update(param_json)

def define_default_config(config_json):
    DEFAULT_CONFIG.clear()
    DEFAULT_CONFIG.update(config_json)


if __name__ == '__main__':

    FLAGS = lambda: None
    # need to get our IP
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    evolver_ip = s.getsockname()[0]
    s.close()



    with open('conf.yml', 'r') as ymlfile:
        conf = yaml.load(ymlfile)
        for element in conf:
            setattr(FLAGS, element, conf[element])

    try:
        task_loop = asyncio.new_event_loop()
        t = PausableThread(target=start_task_loop, args=(task_loop,))
        t.start()        

        define_parameters(DEFAULT_PARAMS)
        socketIO_dpu = SocketIO(FLAGS.dpu_ip, FLAGS.dpu_port)
        dpu_namespace = socketIO_dpu.define(DpuNamespace, '/evolver-dpu')
        PARAM = DEFAULT_PARAMS
        ms = MultiServer()
        app1 = ms.add_app(port=8081)
        sio.attach(app1)
        ms.run_all()
    


    except KeyboardInterrupt:
        socketIO_dpu.disconnect()
