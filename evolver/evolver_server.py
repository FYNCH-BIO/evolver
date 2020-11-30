import socketio
import serial
import evolver
import time
import asyncio
import json
import sys
import os
import yaml
from traceback import print_exc

LOCATION = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))
IMMEDIATE = 'immediate_command_char'
RECURRING = 'recurring_command_char'
CALIBRATIONS_FILENAME = "calibrations.json"

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
    if value is not None:
        if type(value) is list and evolver_conf['experimental_params'][param]['value'] is not None:
            for i, v in enumerate(value):
                if v != 'NaN':
                    evolver_conf['experimental_params'][param]['value'][i] = value[i]
        else:
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
    await sio.emit('commandbroadcast', data, namespace = '/dpu-evolver')

@sio.on('getconfig', namespace = '/dpu-evolver')
async def on_getlastcommands(sid, data):
    global evolver_conf
    await sio.emit('config', evolver_conf, namespace='/dpu-evolver')

@sio.on('getcalibrationnames', namespace = '/dpu-evolver')
async def on_getcalibrationnames(sid, data):
    calibration_names = []
    print("Reteiving cal names...", flush = True)
    try:
        with open(os.path.join(LOCATION, CALIBRATIONS_FILENAME)) as f:
            calibrations = json.load(f)
            for calibration in calibrations:
                calibration_names.append({'name': calibration['name'], 'calibrationType': calibration['calibrationType']})
    except FileNotFoundError:
        print_calibration_file_error()

    await sio.emit("calibrationnames", calibration_names, namespace = '/dpu-evolver')

@sio.on('getfitnames', namespace = '/dpu-evolver')
async def on_getfitnames(sid, data):
    fit_names = []
    print("Retrieving fit names...", flush = True)
    try:
        with open(os.path.join(LOCATION, CALIBRATIONS_FILENAME)) as f:
            calibrations = json.load(f)
            for calibration in calibrations:
                for fit in calibration['fits']:
                    fit_names.append({'name': fit['name'], 'calibrationType': calibration['calibrationType']})
    except FileNotFoundError:
        print_calibration_file_error()

    await sio.emit("fitnames", fit_names, namespace = '/dpu-evolver')

@sio.on('getcalibration', namespace = '/dpu-evolver')
async def on_getcalibration(sid, data):
    try:
        with open(os.path.join(LOCATION, CALIBRATIONS_FILENAME)) as f:
            calibrations = json.load(f)
            for calibration in calibrations:
                if calibration["name"] == data["name"]:
                    await sio.emit('calibration', calibration, namespace = '/dpu-evolver')
                    break
    except FileNotFoundError:
        print_calibration_file_error()

@sio.on('setrawcalibration', namespace = '/dpu-evolver')
async def on_setrawcalibration(sid, data):
    try:
        calibrations = []
        with open(os.path.join(LOCATION, CALIBRATIONS_FILENAME)) as f:
            calibrations = json.load(f)

            # First, delete existing calibration by same name if it exists
            index_to_delete = -1
            for i, calibration in enumerate(calibrations):
                if calibration["name"] == data["name"]:
                    index_to_delete = i
            if index_to_delete >= 0:
                del calibrations[index_to_delete]

            """
                Add the calibration into the list. `data` should be formatted according
                to the cal schema, containing a name, params, and raw field.
            """
            calibrations.append(data)
        with open(os.path.join(LOCATION, CALIBRATIONS_FILENAME), 'w') as f:
            json.dump(calibrations, f)
            await sio.emit('calibrationrawcallback', 'success', namespace = '/dpu-evolver')
    except FileNotFoundError:
        print_calibration_file_error()

@sio.on('setfitcalibration', namespace = '/dpu-evolver')
async def on_setfitcalibrations(sid, data):
    """
        Set a fit calibration into the calibration file. data should contain a `fit` key/value
        formatted according to the cal schema `fit` object. This function will add the fit into the
        fits list for a given calibration.
    """
    try:
        calibrations = []
        with open(os.path.join(LOCATION, CALIBRATIONS_FILENAME)) as f:
            calibrations = json.load(f)
            for calibration in calibrations:
                if calibration["name"] == data["name"]:
                    if calibration.get("fits", None) is not None:
                        index_to_delete = -1
                        for i, fit in enumerate(calibration['fits']):
                            if fit["name"] == data["fit"]["name"]:
                                index_to_delete = i
                        if index_to_delete >= 0:
                            del calibrations["fits"][index_to_delete]
                        calibration["fits"].append(data["fit"])
                    else:
                        calibration["fits"] = [].append(data["fit"])
        with open(os.path.join(LOCATION, CALIBRATIONS_FILENAME), 'w') as f:
            json.dump(calibrations, f)
    except FileNotFoundError:
        print_calibration_file_error()

@sio.on('setactivecal', namespace = '/dpu-evolver')
async def on_setactiveodcal(sid, data):
    try:
        active_calibrations = []
        print("Time to set active cals. Data received: ")
        print(data, flush = True)
        with open(os.path.join(LOCATION, CALIBRATIONS_FILENAME)) as f:
            calibrations = json.load(f)
            for calibration in calibrations:
                active = False
                for fit in calibration['fits']:
                    if fit["name"] in data["calibration_names"]:
                        fit["active"] = True
                        active = True
                    else:
                        fit["active"] = False
                if active:
                    active_calibrations.append(calibration)
            await sio.emit('activecalibrations', active_calibrations, namespace = '/dpu-evolver')
        with open(os.path.join(LOCATION, CALIBRATIONS_FILENAME), 'w') as f:
            json.dump(calibrations, f)
    except FileNotFoundError:
        print_calibration_file_error()

@sio.on('getactivecal', namespace = '/dpu-evolver')
async def on_getactivecal(sid, data):
    try:
        active_calibrations = []
        with open(os.path.join(LOCATION, CALIBRATIONS_FILENAME)) as f:
            calibrations = json.load(f)
            for calibration in calibrations:
                for fit in calibration['fits']:
                    if fit['active']:
                        active_calibrations.append(calibration)
                        break;
        await sio.emit('activecalibrations', active_calibrations, namespace = '/dpu-evolver')
    except FileNotFoundError:
        print_calibration_file_error()

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

def print_calibration_file_error():
    print("Error reading calibrations file.", flush = True)

def clear_broadcast(param=None):
    """ Removes broadcast commands of a specific param from queue """
    global command_queue
    for i, command in enumerate(command_queue):
        if (command['param'] == param or param is None) and command['type'] == RECURRING:
            command_queue.pop(i)
            break

async def run_commands():
    global command_queue, serial_connection
    data = {}
    while len(command_queue) > 0:
        command = command_queue.pop(0)
        try:
            returned_data = serial_communication(command['param'], command['value'], command['type'])
            if returned_data is not None:
                data[command['param']] = returned_data
        except (TypeError, ValueError, serial.serialutil.SerialException, EvolverSerialError) as e:
            print_exc(file = sys.stdout)
            await sio.emit('serialexception', command, namespace = '/dpu-evolver')
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
       for i,command_value in enumerate(output):
            if command_value == 'NaN':
                output[i] = evolver_conf['experimental_params'][param]['value'][i]

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
    time.sleep(.05)

    # Read and process the response
    response = serial_connection.readline().decode('UTF-8', errors='ignore')
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

    # This is necessary to allow the ack to be fully written out to samd21 and for them to fully read
    time.sleep(.05)

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
    broadcast_data['data'] = await run_commands()
    broadcast_data['config'] = evolver_conf['experimental_params']
    if not commands_in_queue:
        print('Broadcasting data', flush = True)
        broadcast_data['ip'] = evolver_conf['evolver_ip']
        broadcast_data['timestamp'] = time.time()
        print(broadcast_data, flush = True)
        await sio.emit('broadcast', broadcast_data, namespace='/dpu-evolver')
