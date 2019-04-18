import socketio
import serial
import evolver
import time
import asyncio
import json
import os
from threading import Thread
import copy

SERIAL = serial.Serial(port="/dev/ttyAMA0", baudrate = 9600, timeout = 2)
SERIAL.reset_input_buffer()
SERIAL.reset_output_buffer()
SERIAL.close()

PARAM = {"od":["we", "turb", "all"], "temp":["xr", "temp","all"], "stir": ["zv", "stir", "all"], "pump": ["st", "pump", "all"], "lxml":["px","lxml","all"]}

DEVICE_CONFIG = 'evolver-config.json'
CAL_CONFIG = 'calibration.json'
CALIBRATIONS_DIR = 'calibrations'
FITTED_DIR = 'fittedCal'
RAWCAL_DIR = 'rawCal'
OD_CAL_DIR = 'od'
TEMP_CAL_DIR = 'temp'

ENDING_SEND = '!'
ENDING_RETURN = 'end'

LOCATION = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))
LOCATIONS = [os.path.join(LOCATION, CALIBRATIONS_DIR),
                os.path.join(LOCATION, CALIBRATIONS_DIR, FITTED_DIR),
                os.path.join(LOCATION, CALIBRATIONS_DIR, RAWCAL_DIR),
                os.path.join(LOCATION, CALIBRATIONS_DIR, FITTED_DIR, OD_CAL_DIR),
                os.path.join(LOCATION, CALIBRATIONS_DIR, FITTED_DIR, TEMP_CAL_DIR),
                os.path.join(LOCATION, CALIBRATIONS_DIR, RAWCAL_DIR, OD_CAL_DIR),
                os.path.join(LOCATION, CALIBRATIONS_DIR, RAWCAL_DIR, TEMP_CAL_DIR)]

command_queue = []
commands_running = False
reading_data = False
last_command = {'lxml': [4095]*32}
evolver_ip = None
sio = socketio.AsyncServer(async_handlers=True)
broadcast_od_power = 4095

@sio.on('connect', namespace = '/dpu-evolver')
async def on_connect(sid, environ):
    print('Connected dpu as server', flush = True)

@sio.on('define', namespace = '/dpu-evolver')
async def on_define(sid, data):
    print('defining params', flush = True)
    define_parameters(data['params'])

@sio.on('disconnect', namespace = '/dpu-evolver')
async def on_disconnect(sid):
    print('Disconnected dpu as Server', flush = True)

@sio.on('command', namespace = '/dpu-evolver')
async def on_command(sid, data):
    global commands_running, command_queue, SERIAL
    print('Received COMMAND', flush = True)
    param = data.get('param')
    message = data.get('message')
    vials = data.get('vials')
    values = data.get('values')
    config = {}
    if param != 'pump':
        config[param] = message
    else:
        if message == 'stop':
            print('stopping all pumps', flush = True)
            config[param] = get_pump_stop_command()
        else:
            config[param] = get_pump_command(message['pumps_binary'], message['pump_time'], message['efflux_pump_time'], message['delay_interval'], message['times_to_repeat'], message['run_efflux'])

    config['push'] = ''
    # Commands go to the front of the queue, then tell the arduinos to not use the serial port.
    run_commands(config = dict(config), reset = True)
    await sio.emit('commandbroadcast', data, namespace='/dpu-evolver')

@sio.on('getlastcommands', namespace = '/dpu-evolver')
async def on_getlastcommands(sid, data):
    global last_command
    await sio.emit('lastcommands', last_command, namespace='/dpu-evolver')

@sio.on('data', namespace = '/dpu-evolver')
async def on_data(sid, data):
    global command_queue, commands_running, evolver_ip
    print('Received request from DATA', flush = True)
    try_count = 0
    config = data['config']

    while commands_running:
        pass
    command_queue.append(config)
    evolver_data = run_commands()
    if evolver_data is None:
        return
    if 'od' in evolver_data and 'temp' in evolver_data and 'NaN' not in evolver_data.get('od') and 'NaN' not in evolver_data.get('temp') and len(evolver_data.get('od', [])) > 0 and len(evolver_data.get('temp',[])) > 0 or try_count > 5:
        evolver_data['ip'] = evolver_ip
        await sio.emit('dataresponse', evolver_data, namespace='/dpu-evolver')

@sio.on('getcalibrationod', namespace = '/dpu-evolver')
async def on_getcalibrationod(sid, data):
    od_filename = ''
    cal = ''
    try:
        with open(os.path.join(LOCATION, CAL_CONFIG)) as f:
            cal_config = json.load(f)
            od_filename = cal_config["activeCalibration"]["od"]["filename"]
    except FileNotFoundError:
        cal_config = {'activeCalibration':{'od':{'filename':''}, 'temp':{'filename':''}}}
        with open(os.path.join(LOCATION, CAL_CONFIG)) as f:
            json.dump(cal_config, f)

    await sio.emit('activecalibrationod', od_filename, namespace='/dpu-evolver')
    try:
        with open(os.path.join(LOCATION, CALIBRATIONS_DIR, FITTED_DIR, OD_CAL_DIR, od_filename), 'r') as f:
            cal = f.read()
    except FileNotFoundError:
        print('Calibration file does not exist: ' + od_filename, flush = True)
    await sio.emit('calibrationod', cal, namespace='/dpu-evolver')

@sio.on('getcalibrationtemp', namespace = '/dpu-evolver')
async def on_getcalibrationtemp(sid, data):
    temp_filename = ''
    cal = ''
    try:
        with open(os.path.join(LOCATION, CAL_CONFIG)) as f:
            cal_config = json.load(f)
            temp_filename = cal_config["activeCalibration"]["temp"]["filename"]
    except FileNotFoundError:
        cal_config = {'activeCalibration':{'od':{'filename':''}, 'temp':{'filename':''}}}
        with open(os.path.join(LOCATION, CAL_CONFIG)) as f:
            json.dump(cal_config, f)

    await sio.emit('activecalibrationtemp', temp_filename, namespace='/dpu-evolver')
    try:
        with open(os.path.join(LOCATION, CALIBRATIONS_DIR, FITTED_DIR, TEMP_CAL_DIR, temp_filename), 'r') as f:
            cal = f.read()
    except FileNotFoundError:
        print('Calibration file does not exist: ' + temp_filename, flush = True)

    await sio.emit('calibrationtemp', cal, namespace='/dpu-evolver')

@sio.on('setcalibrationod', namespace = '/dpu-evolver')
async def on_setcalibrationod(sid, data):
    #ADD OD_FILENAME from returned parameter on data

    od_file = os.path.join(LOCATION, CALIBRATIONS_DIR, FITTED_DIR, OD_CAL_DIR, '.'.join(data['filename'].split('.')[:-1]) + '.txt')
    parameters = reformat_parameters(data['parameters'], caltype = data['caltype'])
    with open(od_file, 'w') as f:
        for param in parameters:
            f.write(','.join(map(str,param)) + '\n')

@sio.on('setcalibrationtemp', namespace = '/dpu-evolver')
async def on_setcalibrationtemp(sid, data):
    print('setting calibration temp fitted', flush = True)
    #ADD TEMP_FILENAME from returned parameter on data
    temp_file = os.path.join(LOCATION, CALIBRATIONS_DIR, FITTED_DIR, TEMP_CAL_DIR, '.'.join(data['filename'].split('.')[:-1]) + '.txt')
    parameters = reformat_parameters(data['parameters'], od = False)
    with open(temp_file, 'w') as f:
        for param in parameters:
            f.write(','.join(map(str,param)) + '\n')

@sio.on('setcalibrationrawod', namespace = '/dpu-evolver')
async def on_setcalibrationrawod(sid, data):
    calibration_path = os.path.join(LOCATION, CALIBRATIONS_DIR, RAWCAL_DIR, OD_CAL_DIR)
    print('saving raw cal', flush = True)
    with open(os.path.join(calibration_path, data['filename']), 'w') as f:
        f.write(json.dumps(data))
    await sio.emit('setcalibrationrawod_callback', 'success' , namespace = '/dpu-evolver')

@sio.on('setcalibrationrawtemp', namespace = '/dpu-evolver')
async def on_setcalibrationrawtemp(sid, data):
    calibration_path = os.path.join(LOCATION, CALIBRATIONS_DIR, RAWCAL_DIR, TEMP_CAL_DIR)
    print('saving raw cal', flush = True)
    with open(os.path.join(calibration_path, data['filename']), 'w') as f:
        f.write(json.dumps(data))
    await sio.emit('setcalibrationrawtemp_callback', 'success', namespace = '/dpu-evolver')

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
    cal = ''
    try:
        with open(os.path.join(LOCATION, CAL_CONFIG)) as f:
        cal_config = json.load(f)
        cal_config["activeCalibration"]["od"]["filename"] = data['filename']
    except FileNotFoundError:
        cal_config = {"activeCalibration":{"od":{"filename":data['filename']}, "temp":{"filename":''}}}

    with open(os.path.join(LOCATION, CAL_CONFIG), 'w') as f:
        f.write(json.dumps(cal_config))

    await sio.emit('activecalibrationod', data['filename'], namespace='/dpu-evolver')
    try:
        with open(os.path.join(LOCATION, CALIBRATIONS_DIR, FITTED_DIR, OD_CAL_DIR, data['filename']), 'r') as f:
            cal = f.read()
    except FileNotFoundError:
        print('Calibration file not found: ' + data['filename'], flush = True)
    await sio.emit('calibrationod', cal, namespace='/dpu-evolver')

@sio.on('setActiveTempCal', namespace = '/dpu-evolver')
async def on_setActiveTempCal(sid, data):
    cal = ''
    try:
        with open(os.path.join(LOCATION, CAL_CONFIG)) as f:
        cal_config = json.load(f)
        cal_config["activeCalibration"]["temp"]["filename"] = data['filename']
    except FileNotFoundError:
        cal_config = {"activeCalibration":{"od":{"filename":'']}, "temp":{"filename":data['filename']}}}

    with open(os.path.join(LOCATION, CAL_CONFIG), 'w') as f:
        f.write(json.dumps(cal_config))
    await sio.emit('activecalibrationtemp', data['filename'], namespace='/dpu-evolver')
    try:
        with open(os.path.join(LOCATION, CALIBRATIONS_DIR, FITTED_DIR, TEMP_CAL_DIR, data['filename']), 'r') as f:
            cal = f.read()
    except FileNotFoundError:
        print('Calibration file not found: ' + data['filename'], flush = True)

    await sio.emit('calibrationtemp', cal, namespace='/dpu-evolver')

@sio.on('getdevicename', namespace = '/dpu-evolver')
async def on_getdevicename(sid, data):
    config_path = os.path.join(LOCATION)
    with open(os.path.join(LOCATION, DEVICE_CONFIG)) as f:
       configJSON = json.load(f)
    await sio.emit('broadcastname', configJSON, namespace = '/dpu-evolver')

@sio.on('setdevicename', namespace = '/dpu-evolver')
async def on_setdevicename(sid, data):
    config_path = os.path.join(LOCATION)
    print('saving device name', flush = True)
    if not os.path.isdir(config_path):
        os.mkdir(config_path)
    with open(os.path.join(config_path, DEVICE_CONFIG), 'w') as f:
        f.write(json.dumps(data))
    await sio.emit('broadcastname', data, namespace = '/dpu-evolver')

@sio.on('setbroadcastodpower', namespace = '/dpu-evolver')
async def on_setbroadcastodpower(sid, data):
    global broadcast_od_power
    broadcast_od_power = int(data)

def addlastcommand(parameter, data):
    global last_command
    if (parameter == 'lxml'):
        for index,value in enumerate(data['message']):
            if not (value == 'NaN'):
                last_command[parameter][index] = value

def reformat_parameters(parameters, od = True, caltype = 'sigmoid'):
    if od:
        if caltype == 'sigmoid':
            reformatted_parameters = [[],[],[],[]]
        if caltype == 'multidim_quad':
            reformatted_parameters = [[],[],[],[],[],[]]
    else:
        reformatted_parameters = [[],[]]
    for vial in parameters:
        for i, param in enumerate(vial):
            reformatted_parameters[i].append(param)
    return reformatted_parameters

def load_calibration():
    with open(os.path.join(LOCATION, 'test_device.json'), 'r') as f:
        return json.loads(f.read())

def run_commands(config = None, reset = False):
    global command_queue, commands_running, SERIAL, reading_data
    commands_running = True
    if config:
        if SERIAL.isOpen():
            SERIAL.close()
            time.sleep(.2)
            command_queue = []
        command_queue = [config]
    data = {}
    while len(command_queue) > 0:
        command_queue = remove_duplicate_commands(command_queue)
        try:
            config = command_queue.pop(0)
        except IndexError:
            break
        try:
            SERIAL = serial.Serial(port="/dev/ttyAMA0", baudrate = 9600, timeout = 2)
            if 'push' in config:
                push_arduino(config)
                time.sleep(.2)
                SERIAL.close()
            else:
                data = ping_arduino(config)
                SERIAL.close()
        except (TypeError, ValueError, serial.serialutil.SerialException)  as e:
            print('Error in running commands - relinquishing serial', flush = True)
            print(e, flush = True)
            SERIAL.close()
            if reset:
                commands_running = False
            return
        # Need to wait to prevent race condition:
        # https://stackoverflow.com/questions/1618141/pyserial-problem-with-arduino-works-with-the-python-shell-but-not-in-a-program/4941880#4941880

        """ When you open the serial port, this causes the Arduino to reset. Since the Arduino takes some time to bootup,
            all the input goes to the bitbucket (or probably to the bootloader which does god knows what with it).
            If you insert a sleep, you wait for the Arduino to come up so your serial code. This is why it works
            interactively; you were waiting the 1.5 seconds needed for the software to come up."""

        time.sleep(.5)
    commands_running = False
    return data

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

def config_to_arduino(key, key_list, header, ending, method):
    global SERIAL
    output = ''
    if method == 'all' and key_list is not None:
        output = header + ','.join(map(str,key_list)) + ', ' + ending
        print('Output to arduino:', flush = True)
        print(output, flush = True)
        SERIAL.write(bytes(output, 'UTF-8'))

    if method == 'indiv' and key_list is not None:
        for x in key_list.split(','):
            output = header + x + ending
            SERIAL.write(bytes(output,'UTF-8'))

def data_from_arduino(key, header, ending):
    global SERIAL
    data_list = None
    if not SERIAL.isOpen():
        return
    received = SERIAL.readline().decode('UTF-8')
    print('Received from arduino:', flush = True)
    print(received, flush = True)
    if received[0:4] == header and received[-3:] == ending:
        data_list = [int(s) for s in received[4:-4].split(',')]
    else:
        print('Data from arduino misconfigured', flush = True)
    return data_list

def ping_arduino(config):
    global PARAM, ENDING_SEND, ENDING_RETURN, SERIAL
    data = {}
    for key, value in config.items():
        config_to_arduino(key, value, PARAM[key][0], ENDING_SEND, PARAM[key][2])
        data[key] = data_from_arduino(key, PARAM[key][1], ENDING_RETURN)
        time.sleep(.5)
    return data

def push_arduino(config):
    global PARAM, ENDING_SEND, SERIAL
    for key, value in config.items():
        if key is not 'push':
            config_to_arduino(key, value, PARAM[key][0], ENDING_SEND, PARAM[key][2])
            if key == 'temp':
                time.sleep(.1)
                SERIAL.reset_input_buffer()

def define_parameters(param_json):
    global PARAM
    PARAM.clear()
    PARAM.update(param_json)

def attach(app):
    global CONFIG, DEFAULT_CONFIG, PARAMS, DEFAULT_PARAMS
    [os.mkdir(d) for d in LOCATIONS if not os.path.isdir(d)]
    sio.attach(app)

def set_ip(ip):
    global evolver_ip
    evolver_ip = ip

async def broadcast():
    global command_queue, commands_running
    print('Got command from BROADCAST', flush = True)
    current_time = time.time()
    config = {'od':[broadcast_od_power] * 16, 'temp':['NaN'] * 16}
    while commands_running:
        pass
    command_queue.append(dict(config))
    data = run_commands()
    if data is None:
        return
    if 'od' in data and 'temp' in data and 'NaN' not in data.get('od') and 'NaN' not in data.get('temp') and len(data.get('od',[])) > 0 and len(data.get('temp',[])) > 0:
        print('Broadcasting data:', flush = True)
        print(data, flush = True)
        data['ip'] = evolver_ip
        await sio.emit('databroadcast', data, namespace='/dpu-evolver')
