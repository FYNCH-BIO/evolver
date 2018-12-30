import socketio
import serial
import evolver_client
import time
import asyncio
import json

SERIAL = serial.Serial(port="/dev/ttyAMA0", baudrate = 9600, timeout = 3)
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

command_queue = []
last_data = None
last_time = None

sio = socketio.AsyncServer()

@sio.on('connect', namespace = '/dpu-evolver')
async def on_connect(sid, environ):
    print('Connected dpu as server')
    define_parameters(DEFAULT_PARAMS)
    PARAM = DEFAULT_PARAMS

@sio.on('define', namespace = '/dpu-evolver')
async def on_define(sid, data):
    print('defining params')
    define_parameters(data['params'])
    define_default_config(data['config'])

@sio.on('disconnect', namespace = '/dpu-evolver')
async def on_disconnect(sid):
    print('Disconnected dpu as Server')

@sio.on('command', namespace = '/dpu-evolver')
async def on_command(sid, data):
    param = data.get('param')
    message = data.get('message')
    vials = data.get('vials')
    values = data.get('values')
    config = {}
    if param != 'pump':
        config[param] = message
    else:
        config[param] = get_pump_command(message['pumps_binary'], message['pump_time'], message['efflux_pump_time'], message['delay_interval'], message['times_to_repeat'], message['run_efflux'])
    
    command_queue.append(dict(config))
    run_commands()

@sio.on('data', namespace = '/dpu-evolver')
async def on_data(sid, data):
    global CONFIG, last_data
    CONFIG = DEFAULT_CONFIG.copy()
    ping_arduino()
    last_data = {'OD': DATA['OD'], 'temp':DATA['temp']} 
    last_time = time.time()
    evolver_client.send_data({'OD': DATA['OD'], 'temp': DATA['temp']})

@sio.on('pingdata', namespace = '/dpu-evolver')
async def on_pingdata(sid, data):
    global last_data, last_time
    if last_data is None or time.time() - last_time > 60 * 10:
        ping_arduino()
        last_data = {'OD': DATA['OD'], 'temp':DATA['temp']} 
        last_time = time.time()
    await sio.emit('dataresponse',last_data, namespace='/dpu-evolver')

@sio.on('getcalibration', namespace = '/dpu-evolver')
async def on_getcalibration(sid, data):
    cal = load_calibration()
    await sio.emit('calibration', cal, namespace='/dpu-evolver')

@sio.on('loadcalibration', namespace = '/dpu-evolver')
async def on_loadcalibration(sid, data):
    pass

def load_calibration():
    with open('test_device.json', 'r') as f:
        return json.loads(f.read())

def run_commands():
    global command_queue, CONFIG
    command_queue = remove_duplicate_commands(command_queue)
    
    while len(command_queue) > 0:
        CONFIG = command_queue.pop(0)
        print('Running command: ' + str(CONFIG))
        push_arduino()

        # Need to wait to prevent race condition:
        # https://stackoverflow.com/questions/1618141/pyserial-problem-with-arduino-works-with-the-python-shell-but-not-in-a-program/4941880#4941880

        """ When you open the serial port, this causes the Arduino to reset. Since the Arduino takes some time to bootup, 
            all the input goes to the bitbucket (or probably to the bootloader which does god knows what with it). 
            If you insert a sleep, you wait for the Arduino to come up so your serial code. This is why it works 
            interactively; you were waiting the 1.5 seconds needed for the software to come up."""
        time.sleep(.5)

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

def config_to_arduino(key, header, ending, method):
    global CONFIG, SERIAL, DEFAULT_CONFIG, DATA
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
    global SERIAL, DATA
    try:
        received = SERIAL.readline().decode('utf-8')
        if received[0:4] == header and received[-3:] == ending:
            dataList = [int(s) for s in received[4:-4].split(',')]
            DATA[key] = dataList
        else:
            DATA[key] = 'NaN'
            print('Problem with data:')
            print(received)
    except (ValueError, serial.serialutil.SerialException) as e:
        print(e)
        DATA[key] = 'NaN'
    SERIAL.close()

def ping_arduino():
    global CONFIG, PARAM, ENDING_SEND, ENDING_RETURN
    for key, value in CONFIG.items():
        config_to_arduino(key, PARAM[key][0], ENDING_SEND, PARAM[key][2])
        data_from_arduino(key, PARAM[key][1], ENDING_RETURN)
    CONFIG.clear()

def push_arduino():
    global CONFIG, PARAM, ENDING_SEND, SERIAL
    for key, value in CONFIG.items():
        config_to_arduino(key, PARAM[key][0], ENDING_SEND, PARAM[key][2])
        SERIAL.close()
    CONFIG.clear()

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
