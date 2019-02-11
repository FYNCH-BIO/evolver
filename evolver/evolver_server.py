import socketio
import serial
import evolver
import time
import asyncio
import json
import os
from threading import Thread
import copy

SERIAL = serial.Serial(port="/dev/ttyAMA0", baudrate = 9600, timeout = 3)
SERIAL.flushInput()
SERIAL.close()

DEFAULT_PARAMS = {"od":["we", "turb", "all"], "temp":["xr", "temp","all"], "stir": ["zv", "stir", "all"], "pump": ["st", "pump", "all"]}
DEFAULT_CONFIG = {'od':[2125] * 16, 'temp':['NaN'] * 16}
PARAM = {}
DATA = {}
CONFIG = {}

CAL_CONFIG = 'calibration.json'
CALIBRATIONS_DIR = 'calibrations'
FITTED_DIR = 'fittedCal'
RAWCAL_DIR = 'rawCal'
OD_CAL_DIR = 'od'
TEMP_CAL_DIR = 'temp'

ENDING_SEND = '!'
ENDING_RETURN = 'end'

LOCATION = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))

command_queue = []
serial_queue = []
last_data = None
last_time = time.time()
running = False
connected = False
serial_available = True
s_running = False
b_running = False
evolver_ip = None
stopread = False
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
    try:
        arduino_serial(False)
        time.sleep(.2)
        run_commands()
        time.sleep(.2)
        arduino_serial(True)
    except OSError:
        pass
    s_running = False

@sio.on('data', namespace = '/dpu-evolver')
async def on_data(sid, data):
    global last_data, DEFAULT_CONFIG, command_queue, evolver_ip, stopread, s_runing
    stopread = False
    config = copy.deepcopy(DEFAULT_CONFIG)
    finished = False
    try_count = 0

    if 'power' in data:
        for i,vial_power in enumerate(data['power']):
            config['od'][i] = vial_power

    s_running = True
    while b_running:
        pass

    while not finished:
        try_count += 1
        command_queue.insert(0,(dict(config)))
        run_commands()
        if 'od' in DATA and 'temp' in DATA and 'NaN' not in DATA.get('od') and 'NaN' not in DATA.get('temp') or try_count > 5:
            last_data = {'od': DATA.get('od', ['NaN'] * 16), 'temp':DATA.get('temp', ['NaN'] * 16), 'ip': evolver_ip}
            if not stopread:
                await sio.emit('dataresponse', last_data, namespace='/dpu-evolver')
            finished = True
    s_running = False

@sio.on('pingdata', namespace = '/dpu-evolver')
async def on_pingdata(sid, data):
    global last_data, DEFAULT_CONFIG, command_queue, stopread
    config = copy.deepcopy(DEFAULT_CONFIG)
    stopread = False
    if 'power' in data:
        for i,vial_power in enumerate(data['power']):
            config['od'][i] = vial_power
    command_queue.append(dict(config))
    if not stopread:
        await sio.emit('dataresponse', last_data, namespace='/dpu-evolver')
    run_commands()
    last_data = {'od': DATA.get('od', ['NaN'] * 16), 'temp':DATA.get('temp',['NaN'] * 16)}

@sio.on('getcalibrationod', namespace = '/dpu-evolver')
async def on_getcalibrationod(sid, data):
    with open(os.path.join(LOCATION, 'calibration.json')) as f:
       CAL_CONFIG = json.load(f)
       OD_FILENAME = CAL_CONFIG["activeCalibration"]["od"]["filename"]
    await sio.emit('activecalibrationod', OD_FILENAME, namespace='/dpu-evolver')
    with open(os.path.join(LOCATION, CALIBRATIONS_DIR, FITTED_DIR, OD_CAL_DIR, OD_FILENAME), 'r') as f:
       cal = f.read()
    await sio.emit('calibrationod', cal, namespace='/dpu-evolver')

@sio.on('getcalibrationtemp', namespace = '/dpu-evolver')
async def on_getcalibrationtemp(sid, data):
    with open(os.path.join(LOCATION, 'calibration.json')) as f:
       CAL_CONFIG = json.load(f)
       TEMP_FILENAME = CAL_CONFIG["activeCalibration"]["temp"]["filename"]
    await sio.emit('activecalibrationtemp', TEMP_FILENAME, namespace='/dpu-evolver')
    with open(os.path.join(LOCATION, CALIBRATIONS_DIR, FITTED_DIR, TEMP_CAL_DIR, TEMP_FILENAME), 'r') as f:
       cal = f.read()
    await sio.emit('calibrationtemp', cal, namespace='/dpu-evolver')

@sio.on('setcalibrationod', namespace = '/dpu-evolver')
async def on_setcalibrationod(sid, data):
    #ADD OD_FILENAME from returned parameter on data
    OD_FILENAME = 'OD_cal.txt'
    od_file = os.path.join(LOCATION, CALIBRATIONS_DIR, FITTED_DIR, OD_CAL_DIR, OD_FILENAME)
    parameters = reformat_parameters(data['parameters'])
    with open(od_file, 'w') as f:
        for param in parameters:
            f.write(','.join(map(str,param)) + '\n')

@sio.on('setcalibrationtemp', namespace = '/dpu-evolver')
async def on_setcalibrationtemp(sid, data):
    #ADD TEMP_FILENAME from returned parameter on data
    TEMP_FILENAME = 'temp_cal.txt'
    temp_file = os.path.join(LOCATION, CALIBRATIONS_DIR, FITTED_DIR, TEMP_CAL_DIR, TEMP_FILENAME)
    parameters = reformat_parameters(data['parameters'], od = False)
    with open(temp_file, 'w') as f:
        for param in parameters:
            f.write(','.join(map(str,param)) + '\n')

@sio.on('setcalibrationrawod', namespace = '/dpu-evolver')
async def on_setcalibrationrawod(sid, data):
    calibration_path = os.path.join(LOCATION, CALIBRATIONS_DIR, RAWCAL_DIR, OD_CAL_DIR)
    print('saving raw cal')
    if not os.path.isdir(calibration_path):
        os.mkdir(calibration_path)

    with open(os.path.join(calibration_path, data['filename']), 'w') as f:
        f.write(json.dumps(data))

@sio.on('setcalibrationrawtemp', namespace = '/dpu-evolver')
async def on_setcalibrationrawtemp(sid, data):
    calibration_path = os.path.join(LOCATION, CALIBRATIONS_DIR, RAWCAL_DIR, TEMP_CAL_DIR)
    print('saving raw cal')
    if not os.path.isdir(calibration_path):
        os.mkdir(calibration_path)

    with open(os.path.join(calibration_path, data['filename']), 'w') as f:
        f.write(json.dumps(data))

@sio.on('getcalibrationrawod', namespace = '/dpu-evolver')
async def on_getcalibrationrawod(sid, data):
    calibration_path = os.path.join(LOCATION, CALIBRATIONS_DIR, RAWCAL_DIR, OD_CAL_DIR)
    with open(os.path.join(calibration_path, data['filename']), 'r') as f:
        await sio.emit('calibrationrawod', json.loads(f.read()), namespace = '/dpu-evolver')

@sio.on('getcalibrationrawtemp', namespace = '/dpu-evolver')
async def on_getcalibrationrawtemp(sid, data):
    calibration_path = os.path.join(LOCATION, CALIBRATIONS_DIR, RAWCAL_DIR, TEMP_CAL_DIR)
    with open(os.path.join(calibration_path, data['filename']), 'r') as f:
        await sio.emit('calibrationrawtemp', json.loads(f.read()), namespace = '/dpu-evolver')

@sio.on('getcalibrationfilenamesod', namespace = '/dpu-evolver')
async def on_getcalibrationfilenamesod(sid, data):
    files = os.listdir(os.path.join(LOCATION, CALIBRATIONS_DIR, RAWCAL_DIR, OD_CAL_DIR))
    await sio.emit('odfilenames', files, namespace = '/dpu-evolver')

@sio.on('getcalibrationfilenamestemp', namespace = '/dpu-evolver')
async def on_getcalibrationfilenamesod(sid, data):
    files = os.listdir(os.path.join(LOCATION, CALIBRATIONS_DIR, RAWCAL_DIR, TEMP_CAL_DIR))
    await sio.emit('tempfilenames', files, namespace = '/dpu-evolver')

@sio.on('getfittedcalibrationfilenamesod', namespace = '/dpu-evolver')
async def on_getfittedcalibrationfilenamesod(sid, data):
    files = os.listdir(os.path.join(LOCATION, CALIBRATIONS_DIR, FITTED_DIR, OD_CAL_DIR))
    await sio.emit('odfittedfilenames', files, namespace = '/dpu-evolver')

@sio.on('getfittedcalibrationfilenamestemp', namespace = '/dpu-evolver')
async def on_getfittedcalibrationfilenamesod(sid, data):
    files = os.listdir(os.path.join(LOCATION, CALIBRATIONS_DIR, FITTED_DIR, TEMP_CAL_DIR))
    await sio.emit('tempfittedfilenames', files, namespace = '/dpu-evolver')

@sio.on('setActiveODCal', namespace = '/dpu-evolver')
async def on_setActiveODCal(sid, data):
    with open(os.path.join(LOCATION, 'calibration.json')) as f:
       CAL_CONFIG = json.load(f)
       CAL_CONFIG["activeCalibration"]["od"]["filename"] = data['filename']
    with open(os.path.join(LOCATION, 'calibration.json'), 'w') as f:
        f.write(json.dumps(CAL_CONFIG))
    await sio.emit('activecalibrationod', data['filename'], namespace='/dpu-evolver')
    with open(os.path.join(LOCATION, CALIBRATIONS_DIR, FITTED_DIR, OD_CAL_DIR, data['filename']), 'r') as f:
       cal = f.read()
    await sio.emit('calibrationod', cal, namespace='/dpu-evolver')

@sio.on('setActiveTempCal', namespace = '/dpu-evolver')
async def on_setActiveTempCal(sid, data):
    with open(os.path.join(LOCATION, 'calibration.json')) as f:
       CAL_CONFIG = json.load(f)
       CAL_CONFIG["activeCalibration"]["temp"]["filename"] = data['filename']
    with open(os.path.join(LOCATION, 'calibration.json'), 'w') as f:
        f.write(json.dumps(CAL_CONFIG))
    await sio.emit('activecalibrationtemp', data['filename'], namespace='/dpu-evolver')
    with open(os.path.join(LOCATION, CALIBRATIONS_DIR, FITTED_DIR, TEMP_CAL_DIR, data['filename']), 'r') as f:
       cal = f.read()
    await sio.emit('calibrationtemp', cal, namespace='/dpu-evolver')

@sio.on('stopread', namespace = '/dpu-evolver')
async def on_stopread(sid, data):
    global stopread
    stopread = True

def reformat_parameters(parameters, od = True):
    if od:
        reformatted_parameters = [[],[],[],[]]
    else:
        reformatted_parameters = [[],[]]
    for vial in parameters:
        for i, param in enumerate(vial):
            reformatted_parameters[i].append(param)
    return reformatted_parameters

def load_calibration():
    with open(os.path.join(LOCATION, 'test_device.json'), 'r') as f:
        return json.loads(f.read())

def run_commands():
    global command_queue, running
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
        config = copy.deepcopy(DEFAULT_CONFIG)
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
    cfg = copy.deepcopy(DEFAULT_CONFIG)
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
    global last_data, last_time, DEFAULT_CONFIG, command_queue, DATA, s_running, connected, b_running
    current_time = time.time()
    if s_running or not connected:
        return

    config = copy.deepcopy(DEFAULT_CONFIG)
    b_running = True
    command_queue.append(dict(config))
    run_commands()
    if 'od' in DATA and 'temp' in DATA and 'NaN' not in DATA.get('od') and 'NaN' not in DATA.get('temp'):
        last_data = {'od': DATA['od'], 'temp':DATA['temp']}
        last_time = time.time()
        await sio.emit('databroadcast', last_data, namespace='/dpu-evolver')
    b_running = False
