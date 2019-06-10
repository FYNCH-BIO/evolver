import socketio
import serial
import evolver
import time
import asyncio
import json
import os
import yaml
from traceback import print_exc

LOCATION = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))
IMMEDIATE = 'immediate_command_char'
RECURRING = 'recurring_command_char'

evolver_conf = {}
serial_connection = None
command_queue = []
sio = socketio.AsyncServer(async_handlers=True)

class EvolverSerialError(Exception):
    pass

@sio.on('connect', namespace = '/dpu-evolver')
async def on_connect(sid, environ):
    print('Connected dpu as server', flush = True)

@sio.on('disconnect', namespace = '/dpu-evolver')
async def on_disconnect(sid):
    print('Disconnected dpu as Server', flush = True)

@sio.on('command', namespace = '/dpu-evolver')
async def on_command(sid, data):
    global command_queue, evolver_conf
    print('Received COMMAND', flush = True)
    param = data.get('param', None)
    value = data.get('value', None)
    immediate = data.get('immediate', None)
    recurring = data.get('recurring', None)
    fields_expected_outgoing = data.get('fields_expected_outgoing', None)
    fields_expected_incoming = data.get('fields_expected_incoming', None)

    # Update the configuration for the param
    # TODO - make parameters generalized
    evolver_conf['experimental_params'][param]['value'] = value
    if recurring is not None:
        evolver_conf['experimental_params'][param]['recurring'] = recurring
    if fields_expected_outgoing is not None:
        evolver_conf['experimental_params'][param]['fields_expected_outgoing'] = fields_expected_outgoing
    if fields_expected_incoming is not None:
        evolver_conf['experimental_params'][param]['fields_expected_incoming'] = fields_expected_incoming


    # Save to config the values sent in for the parameter
    with open(os.path.realpath(os.path.join(os.getcwd(),os.path.dirname(__file__), evolver.CONF_FILENAME)), 'w') as ymlfile:
        yaml.dump(evolver_conf, ymlfile)

    if immediate:
        clear_broadcast(param)
        command_queue.insert(0, {'param': param, 'value': value, 'type': IMMEDIATE})

@sio.on('getconfig', namespace = '/dpu-evolver')
async def on_getlastcommands(sid, data):
    global evolver_conf
    await sio.emit('config', evolver_conf, namespace='/dpu-evolver')

@sio.on('getcalibrationod', namespace = '/dpu-evolver')
async def on_getcalibrationod(sid, data):
    with open(os.path.join(LOCATION, evolver_conf['calibration'])) as f:
        cal_config = json.load(f)
        od_filename = cal_config['activeCalibration']['od']['filename']
    await sio.emit('activecalibrationod', od_filename, namespace='/dpu-evolver')
    with open(os.path.join(LOCATION, evolver_conf['calibrations_directory'], evolver_conf['fitted_data_directory'], evolver_conf['od_calibration_directory'], od_filename), 'r') as f:
        cal = f.read()
    await sio.emit('calibrationod', cal, namespace='/dpu-evolver')

@sio.on('getcalibrationtemp', namespace = '/dpu-evolver')
async def on_getcalibrationtemp(sid, data):
    with open(os.path.join(LOCATION, evolver_conf['calibration'])) as f:
        cal_config = json.load(f)
        temp_filename = cal_config['activeCalibration']['temp']['filename']
    await sio.emit('activecalibrationtemp', temp_filename, namespace='/dpu-evolver')
    with open(os.path.join(LOCATION, evolver_conf['calibrations_directory'], evolver_conf['fitted_data_directory'], evolver_conf['temp_calibration_directory'], temp_filename), 'r') as f:
        cal = f.read()
    await sio.emit('calibrationtemp', cal, namespace='/dpu-evolver')

@sio.on('setcalibrationod', namespace = '/dpu-evolver')
async def on_setcalibrationod(sid, data):
    #ADD OD_FILENAME from returned parameter on data

    od_file = os.path.join(LOCATION, evolver_conf['calibrations_directory'], evolver_conf['fitted_data_directory'], evolver_conf['od_calibration_directory'], '.'.join(data['filename'].split('.')[:-1]) + '.txt')
    parameters = reformat_parameters(data['parameters'], caltype = data['caltype'])
    with open(od_file, 'w') as f:
        for param in parameters:
            f.write(','.join(map(str,param)) + '\n')

@sio.on('setcalibrationtemp', namespace = '/dpu-evolver')
async def on_setcalibrationtemp(sid, data):
    print('setting calibration temp fitted', flush = True)
    #ADD TEMP_FILENAME from returned parameter on data
    temp_file = os.path.join(LOCATION, evolver_conf['calibrations_directory'], evolver_conf['fitted_data_directory'], evolver_conf['temp_calibration_directory'], '.'.join(data['filename'].split('.')[:-1]) + '.txt')
    parameters = reformat_parameters(data['parameters'], od = False)
    with open(temp_file, 'w') as f:
        for param in parameters:
            f.write(','.join(map(str,param)) + '\n')

@sio.on('setcalibrationrawod', namespace = '/dpu-evolver')
async def on_setcalibrationrawod(sid, data):
    calibration_path = os.path.join(LOCATION, evolver_conf['calibrations_directory'], evolver_conf['raw_data_directory'], evolver_conf['od_calibration_directory'])
    print('saving raw cal', flush = True)
    with open(os.path.join(calibration_path, data['filename']), 'w') as f:
        f.write(json.dumps(data))
    await sio.emit('setcalibrationrawod_callback', 'success' , namespace = '/dpu-evolver')

@sio.on('setcalibrationrawtemp', namespace = '/dpu-evolver')
async def on_setcalibrationrawtemp(sid, data):
    calibration_path = os.path.join(LOCATION, evolver_conf['calibrations_directory'], evolver_conf['raw_data_directory'], evolver_conf['temp_calibration_directory'])
    print('saving raw cal', flush = True)
    with open(os.path.join(calibration_path, data['filename']), 'w') as f:
        f.write(json.dumps(data))
    await sio.emit('setcalibrationrawtemp_callback', 'success', namespace = '/dpu-evolver')

@sio.on('getcalibrationrawod', namespace = '/dpu-evolver')
async def on_getcalibrationrawod(sid, data):
    calibration_path = os.path.join(LOCATION, evolver_conf['calibrations_directory'], evolver_conf['raw_data_directory'], evolver_conf['od_calibration_directory'])
    with open(os.path.join(calibration_path, data['filename']), 'r') as f:
        await sio.emit('calibrationrawod', json.loads(f.read()), namespace = '/dpu-evolver')

@sio.on('getcalibrationrawtemp', namespace = '/dpu-evolver')
async def on_getcalibrationrawtemp(sid, data):
    calibration_path = os.path.join(LOCATION, evolver_conf['calibrations_directory'], evolver_conf['raw_data_directory'], evolver_conf['temp_calibration_directory'])
    with open(os.path.join(calibration_path, data['filename']), 'r') as f:
        await sio.emit('calibrationrawtemp', json.loads(f.read()), namespace = '/dpu-evolver')

@sio.on('getcalibrationfilenamesod', namespace = '/dpu-evolver')
async def on_getcalibrationfilenamesod(sid, data):
    files = os.listdir(os.path.join(LOCATION, evolver_conf['calibrations_directory'], evolver_conf['raw_data_directory'], evolver_conf['od_calibration_directory']))
    await sio.emit('odfilenames', files, namespace = '/dpu-evolver')

@sio.on('getcalibrationfilenamestemp', namespace = '/dpu-evolver')
async def on_getcalibrationfilenamesod(sid, data):
    files = os.listdir(os.path.join(LOCATION, evolver_conf['calibrations_directory'], evolver_conf['raw_data_directory'], evolver_conf['temp_calibration_directory']))
    await sio.emit('tempfilenames', files, namespace = '/dpu-evolver')

@sio.on('getfittedcalibrationfilenamesod', namespace = '/dpu-evolver')
async def on_getfittedcalibrationfilenamesod(sid, data):
    files = os.listdir(os.path.join(LOCATION, evolver_conf['calibrations_directory'], evolver_conf['fitted_data_directory'], evolver_conf['od_calibration_directory']))
    await sio.emit('odfittedfilenames', files, namespace = '/dpu-evolver')

@sio.on('getfittedcalibrationfilenamestemp', namespace = '/dpu-evolver')
async def on_getfittedcalibrationfilenamesod(sid, data):
    files = os.listdir(os.path.join(LOCATION, evolver_conf['calibrations_directory'], evolver_conf['fitted_data_directory'], evolver_conf['temp_calibration_directory']))
    await sio.emit('tempfittedfilenames', files, namespace = '/dpu-evolver')

@sio.on('setActiveODCal', namespace = '/dpu-evolver')
async def on_setActiveODCal(sid, data):
    cal = ''
    try:
        with open(os.path.join(LOCATION, evolver_conf['calibration'])) as f:
            cal_config = json.load(f)
            cal_config["activeCalibration"]["od"]["filename"] = data['filename']
    except FileNotFoundError:
        cal_config = {"activeCalibration":{"od":{"filename":data['filename']}, "temp":{"filename":''}}}

    with open(os.path.join(LOCATION, evolver_conf['calibration']), 'w') as f:
        f.write(json.dumps(cal_config))

    await sio.emit('activecalibrationod', data['filename'], namespace='/dpu-evolver')
    try:
        with open(os.path.join(LOCATION, evolver_conf['calibrations_directory'], evolver_conf['fitted_data_directory'], evolver_conf['od_calibration_directory'], data['filename']), 'r') as f:
            cal = f.read()
    except FileNotFoundError:
        print('Calibration file cannot be found: ' + data['filename'], flush = True)
    await sio.emit('calibrationod', cal, namespace='/dpu-evolver')

@sio.on('setActiveTempCal', namespace = '/dpu-evolver')
async def on_setActiveTempCal(sid, data):
    cal = ''
    try:
        with open(os.path.join(LOCATION, evolver_conf['calibration'])) as f:
            cal_config = json.load(f)
            cal_config["activeCalibration"]["temp"]["filename"] = data['filename']
    except FileNotFoundError:
        cal_config = {"activeCalibration":{"od":{"filename":''}, "temp":{"filename":data['filename']}}}

    with open(os.path.join(LOCATION, evolver_conf['calibration']), 'w') as f:
        f.write(json.dumps(cal_config))
    await sio.emit('activecalibrationtemp', data['filename'], namespace='/dpu-evolver')
    try:
        with open(os.path.join(LOCATION, evolver_conf['calibrations_directory'], evolver_conf['fitted_data_directory'], evolver_conf['temp_calibration_directory'], data['filename']), 'r') as f:
            cal = f.read()
    except FileNotFoundError:
        print('Calibration file cannot be found: ' + data['filename'], flush = True)

    await sio.emit('calibrationtemp', cal, namespace='/dpu-evolver')

@sio.on('getdevicename', namespace = '/dpu-evolver')
async def on_getdevicename(sid, data):
    config_path = os.path.join(LOCATION)
    with open(os.path.join(LOCATION, evolver_conf['device'])) as f:
       configJSON = json.load(f)
    await sio.emit('broadcastname', configJSON, namespace = '/dpu-evolver')

@sio.on('setdevicename', namespace = '/dpu-evolver')
async def on_setdevicename(sid, data):
    config_path = os.path.join(LOCATION)
    print('saving device name', flush = True)
    if not os.path.isdir(config_path):
        os.mkdir(config_path)
    with open(os.path.join(config_path, evolver_conf['device']), 'w') as f:
        f.write(json.dumps(data))
    await sio.emit('broadcastname', data, namespace = '/dpu-evolver')

@sio.on('setbroadcastodpower', namespace = '/dpu-evolver')
async def on_setbroadcastodpower(sid, data):
    global broadcast_od_power
    broadcast_od_power = int(data)

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

def clear_broadcast(param=None):
    """ Removes broadcast commands of a specific param from queue """
    global command_queue
    for i, command in enumerate(command_queue):
        if (command['param'] == param or param is None) and command['type'] == RECURRING:
            command_queue.pop(i)
            break

def run_commands():
    global command_queue, serial_connection
    data = {}
    while len(command_queue) > 0:
        command = command_queue.pop(0)
        try:
            returned_data = serial_communication(command['param'], command['value'], command['type'])
            if returned_data is not None:
                data[command['param']] = returned_data
        except (TypeError, ValueError, serial.serialutil.SerialException, EvolverSerialError) as e:
            print(str(e.__class__.__name__), flush = True)
            print_exc()
    return data

def serial_communication(param, value, comm_type):
    serial_connection.reset_input_buffer()
    serial_connection.reset_output_buffer()
    output = []

    # Check that parameters being sent to arduino match expected values
    if comm_type == RECURRING:
        output.append(evolver_conf[RECURRING])
    if comm_type == IMMEDIATE:
        output.append(evolver_conf[IMMEDIATE])

    if type(value) is list:
       output = output + list(map(str,value))
    else:
        output.append(value)

    fields_expected_outgoing = evolver_conf['experimental_params'][param]['fields_expected_outgoing']
    fields_expected_incoming = evolver_conf['experimental_params'][param]['fields_expected_incoming']
    if len(output) is not fields_expected_outgoing:
        raise EvolverSerialError('Error: Number of fields outgoing for ' + param + ' different from expected\n\tExpected: ' + str(fields_expected_outgoing) + '\n\tFound: ' + str(len(output)))

    # Construct the actual string and write out on the serial buffer
    serial_output = param + ','.join(output) + ',' + evolver_conf['serial_end_outgoing']
    print(serial_output)
    serial_connection.write(bytes(serial_output, 'UTF-8'))

    # Read and process the response
    response = serial_connection.readline().decode('UTF-8')
    print(response, flush = True)
    address = response[0:len(param)]
    if address != param:
        raise EvolverSerialError('Error: Response has incorrect address.\n\tExpected: ' + param + '\n\tFound:' + address)
    if response.find(evolver_conf['serial_end_incoming']) != len(response) - len(evolver_conf['serial_end_incoming']):
        raise EvolverSerialError('Error: Response did not have valid serial communication termination string!\n\tExpected: ' +  evolver_conf['serial_end_incoming'] + '\n\tFound: ' + response[len(response) - 3:])

    # Remove the address and ending from the response string and convert to a list
    returned_data = response[len(param):len(response) - len(evolver_conf['serial_end_incoming']) - 1].split(',')

    if len(returned_data) != fields_expected_incoming:
        raise EvolverSerialError('Error: Number of fields recieved for ' + param + ' different from expected\n\tExpected: ' + str(fields_expected_incoming) + '\n\tFound: ' + str(len(returned_data)))

    if returned_data[0] == evolver_conf['echo_response_char'] and output[1:] != returned_data[1:]:
        raise EvolverSerialError('Error: Value returned by echo different from values sent.\n\tExpected:' + str(output[1:]) + '\n\tFound: ' + str(value))
    elif returned_data[0] != evolver_conf['data_response_char'] and returned_data[0] != evolver_conf['echo_response_char']:
        raise EvolverSerialError('Error: Incorect response character.\n\tExpected: ' + evolver_conf['data_response_char'] + '\n\tFound: ' + returned_data[0])

    # ACKNOWLEDGE - lets arduino know it's ok to run any commands (super important!)
    serial_output = [''] * fields_expected_outgoing
    serial_output[0] = evolver_conf['acknowledge_char']
    serial_output = param + ','.join(serial_output) + ',' + evolver_conf['serial_end_outgoing']
    print(serial_output, flush = True)
    serial_connection.write(bytes(serial_output, 'UTF-8'))

    if returned_data[0] == evolver_conf['data_response_char']:
        returned_data = returned_data[1:]
    else:
        returned_data = None

    return returned_data

def attach(app, conf):
    """
        Attach the server to the web application.
        Initialize server from config
    """
    global evolver_conf, serial_connection

    sio.attach(app)
    evolver_conf = conf
    # Create directories if they don't exist
    locations = [os.path.join(LOCATION, evolver_conf['calibrations_directory']),
                    os.path.join(LOCATION, evolver_conf['calibrations_directory'], evolver_conf['fitted_data_directory']),
                    os.path.join(LOCATION, evolver_conf['calibrations_directory'], evolver_conf['raw_data_directory']),
                    os.path.join(LOCATION, evolver_conf['calibrations_directory'], evolver_conf['fitted_data_directory'], evolver_conf['od_calibration_directory']),
                    os.path.join(LOCATION, evolver_conf['calibrations_directory'], evolver_conf['fitted_data_directory'], evolver_conf['temp_calibration_directory']),
                    os.path.join(LOCATION, evolver_conf['calibrations_directory'], evolver_conf['raw_data_directory'], evolver_conf['od_calibration_directory']),
                    os.path.join(LOCATION, evolver_conf['calibrations_directory'], evolver_conf['raw_data_directory'], evolver_conf['temp_calibration_directory'])]
    [os.mkdir(d) for d in locations if not os.path.isdir(d)]

    # Set up the serial comms
    serial_connection = serial.Serial(port=evolver_conf['serial_port'], baudrate = evolver_conf['serial_baudrate'], timeout = evolver_conf['serial_timeout'])

def get_num_commands():
    global command_queue
    return len(command_queue)

async def broadcast(commands_in_queue):
    global command_queue
    broadcast_data = {}
    clear_broadcast()
    if not commands_in_queue:
        for param, config in evolver_conf['experimental_params'].items():
            if config['recurring']:
                command_queue.append({'param': param, 'value': config['value'], 'type':RECURRING})
    # Always run commands so that IMMEDIATE requests occur. RECURRING requests only happen if no commands in queue
    broadcast_data['data'] = run_commands()
    broadcast_data['config'] = evolver_conf['experimental_params']
    if not commands_in_queue:
        print('Broadcasting data', flush = True)
        print(broadcast_data)
        broadcast_data['ip'] = evolver_conf['evolver_ip']
        await sio.emit('broadcast', broadcast_data, namespace='/dpu-evolver')
