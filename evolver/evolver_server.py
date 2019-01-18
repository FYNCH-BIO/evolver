import socketio
import serial
import evolver
import time
import asyncio
import json
import os
from threading import Thread

SERIAL = serial.Serial(port="/dev/ttyAMA0", baudrate = 9600, timeout = 3)
SERIAL.flushInput()
SERIAL.close()

DEFAULT_PARAMS = {"OD":["we", "turb", "all"], "temp":["xr", "temp","all"], "stir": ["zv", "stir", "all"], "pump": ["st", "pump", "all"]}
DEFAULT_CONFIG = {'OD':[2125] * 16, 'temp':['NaN'] * 16}
PARAM = {}
DATA = {}
CONFIG = {}

ENDING_SEND = '!'
ENDING_RETURN = 'end'

command_queue = []
serial_queue = []
last_data = None
last_time = time.time()
running = False
connected = False
serial_available = True
s_running = False
evolver_ip = None
sio = socketio.AsyncServer(async_handlers=True)

@sio.on('connect', namespace = '/dpu-evolver')
async def on_connect(sid, environ):
    print('Connected dpu as server')
    global DEFAULT_PARAMS, PARAM, connected
    PARAM = DEFAULT_PARAMS
    connected = True

@sio.on('define', namespace = '/dpu-evolver')
async def on_define(sid, data):
    print('defining params')
    define_parameters(data['params'])
    define_default_config(data['config'])

@sio.on('disconnect', namespace = '/dpu-evolver')
async def on_disconnect(sid):
    global connected
    print('Disconnected dpu as Server')
    connected = False

@sio.on('command', namespace = '/dpu-evolver')
async def on_command(sid, data):
    global s_running
    param = data.get('param')
    message = data.get('message')
    vials = data.get('vials')
    values = data.get('values')
    config = {}
    if param != 'pump':
        config[param] = message
    else:
        if message == 'stop':
            config[param] = get_pump_stop_command()
        else:
            config[param] = get_pump_command(message['pumps_binary'], message['pump_time'], message['efflux_pump_time'], message['delay_interval'], message['times_to_repeat'], message['run_efflux'])

    config['push'] = ''
    # Commands go to the front of the queue, then tell the arduinos to not use the serial port.
    s_running = True
    command_queue.insert(0, dict(config))
    arduino_serial(False)
    time.sleep(.2)
    run_commands()
    time.sleep(.2)
    arduino_serial(True)
    s_running = False

@sio.on('data', namespace = '/dpu-evolver')
async def on_data(sid, data):
    global CONFIG, last_data, DEFAULT_CONFIG, command_queue, evolver_ip
    CONFIG = DEFAULT_CONFIG.copy()
    command_queue.append(dict(CONFIG))
    run_commands()
    last_data = {'OD': DATA.get('OD', ['NaN'] * 16), 'temp':DATA.get('temp', ['NaN'] * 16), 'ip': evolver_ip}
    await sio.emit('dataresponse', last_data, namespace='/dpu-evolver')

# TODO: Remove redundant function
@sio.on('pingdata', namespace = '/dpu-evolver')
async def on_pingdata(sid, data):
    global last_data, CONFIG, DEFAULT_CONFIG, command_queue
    CONFIG = DEFAULT_CONFIG.copy()
    command_queue.append(dict(CONFIG))
    run_commands()
    last_data = {'OD': DATA.get('OD', ['NaN'] * 16), 'temp':DATA.get('temp', ['NaN'] * 16)}
    await sio.emit('dataresponse', last_data, namespace='/dpu-evolver')

@sio.on('getcalibration', namespace = '/dpu-evolver')
async def on_getcalibration(sid, data):
    cal = load_calibration()
    await sio.emit('calibration', cal, namespace='/dpu-evolver')

@sio.on('loadcalibration', namespace = '/dpu-evolver')
async def on_loadcalibration(sid, data):
    pass

def load_calibration():
    location = os.path.realpath(os.path.join(os.getcwd(),
        os.path.dirname(__file__)))
    with open(os.path.join(location, 'test_device.json'), 'r') as f:
        return json.loads(f.read())

def run_commands():
    global command_queue, CONFIG, running
    running = True
    command_queue = remove_duplicate_commands(command_queue)
    while len(command_queue) > 0:
        command_queue = remove_duplicate_commands(command_queue)
        config = command_queue.pop(0)
        if 'push' in config:
            push_arduino(config)
        else:
            ping_arduino(config)

        # Need to wait to prevent race condition:
        # https://stackoverflow.com/questions/1618141/pyserial-problem-with-arduino-works-with-the-python-shell-but-not-in-a-program/4941880#4941880

        """ When you open the serial port, this causes the Arduino to reset. Since the Arduino takes some time to bootup,
            all the input goes to the bitbucket (or probably to the bootloader which does god knows what with it).
            If you insert a sleep, you wait for the Arduino to come up so your serial code. This is why it works
            interactively; you were waiting the 1.5 seconds needed for the software to come up."""
        time.sleep(.5)
    running = False

# TODO - refactor this
def get_pump_command(pumps_binary, num_secs, num_secs_efflux, interval, times_to_repeat, run_efflux):
    num_secs = float(num_secs)
    empty_vals = [0] * 11

    if run_efflux:
        run_efflux = 1
    else:
        run_efflux = 0

    # Command structure: "st<MODE><time to pump>,<time to pump efflux extra>,<delay interval>,<times to repeat>,<run efflux simultaneously>,<vials binary>,0,0,0,0,0,0,0,0,0,0,0 !"
    pump_cmd = ["p", '{:.2f}'.format(num_secs), '{:.2f}'.format(num_secs_efflux), interval, times_to_repeat, run_efflux, pumps_binary] + empty_vals

    return pump_cmd

def get_pump_stop_command():
    empty_vals = [0] * 17
    pump_cmd = ['o'] + empty_vals
    return pump_cmd

def remove_duplicate_commands(command_queue):
    commands_seen = set()
    commands_to_delete = []

    # Traverse list in reverse to keep the last sent request by user/code only
    # Added bonus - don't have to worry about index shifts after deleting since deleting from end to beginning
    for i, command in enumerate(reversed(command_queue)):
       for key, value in command.items():
            if key == 'pump':
                command_check = str(value)
            else:
                command_check = key
            if command_check in commands_seen:
                # store index for non-revered list
                commands_to_delete.append(len(command_queue) - 1 - i)
            commands_seen.add(command_check)

    for command_index in commands_to_delete:
        del command_queue[command_index]

    return command_queue

def config_to_arduino(key, header, ending, method, config):
    global SERIAL, DEFAULT_CONFIG, DATA, s_running
    if not config:
        config = DEFAULT_CONFIG.copy()
    if 'temp' in config:
        DEFAULT_CONFIG['temp'] = config['temp']
    myList = config.get(key)

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
    global SERIAL, DATA, serial_available
    try:
        if serial_available:
            received = SERIAL.readline().decode('utf-8')
        if received[0:4] == header and received[-3:] == ending:
            dataList = [int(s) for s in received[4:-4].split(',')]
            DATA[key] = dataList
        else:
            DATA[key] = ['NaN'] * 16
    except (TypeError, ValueError, serial.serialutil.SerialException) as e:
        DATA[key] = ['NaN'] * 16
    if serial_available:
        try:
            SERIAL.close()
        except (TypeError, ValueError, serial.serialutil.SerialException) as e:
            pass

def ping_arduino(config):
    global PARAM, ENDING_SEND, ENDING_RETURN, SERIAL, serial_available
    if not SERIAL.isOpen():
        for key, value in config.items():
            if not serial_available:
                break
            config_to_arduino(key, PARAM[key][0], ENDING_SEND, PARAM[key][2], config)
            if serial_available:
                data_from_arduino(key, PARAM[key][1], ENDING_RETURN)

def push_arduino(config):
    global PARAM, ENDING_SEND, SERIAL
    if not SERIAL.isOpen():
        for key, value in config.items():
            if key is not 'push':
                config_to_arduino(key, PARAM[key][0], ENDING_SEND, PARAM[key][2], config)
                SERIAL.close()

def arduino_serial(can_use_serial):
    global SERIAL, DEFAULT_CONFIG, PARAM, ENDING_SEND, serial_available
    cfg = DEFAULT_CONFIG.copy()
    serial_available = can_use_serial
    # Reset the serial connection
    if SERIAL.isOpen():
        SERIAL.close()
    SERIAL.open()
    for key, value in cfg.items():
        header = PARAM[key][0]
        message = "sf"
        if can_use_serial:
            message = "st"
        output = header + ','.join([message] + ["0"] * 15) + " " + ENDING_SEND
        print(output)
        SERIAL.write(bytes(output, 'UTF-8'))
    SERIAL.close()

def define_parameters(param_json):
    global PARAM
    PARAM.clear()
    PARAM.update(param_json)

def define_default_config(config_json):
    global DEFAULT_CONFIG
    DEFAULT_CONFIG.clear()
    DEFAULT_CONFIG.update(config_json)

def attach(app):
    sio.attach(app)

def is_connected():
    global connected
    return connected

def set_ip(ip):
    global evolver_ip
    evolver_ip = ip

async def broadcast():
    global last_data, last_time, CONFIG, DEFAULT_CONFIG, command_queue, DATA, s_running, connected
    current_time = time.time()
    if s_running or not connected:
        return

    CONFIG = DEFAULT_CONFIG.copy()
    command_queue.append(dict(CONFIG))
    run_commands()
    if 'OD' in DATA and 'temp' in DATA and 'NaN' not in DATA.get('OD') and 'NaN' not in DATA.get('temp'):
        last_data = {'OD': DATA['OD'], 'temp':DATA['temp']}
        last_time = time.time()
        await sio.emit('databroadcast', last_data, namespace='/dpu-evolver')
