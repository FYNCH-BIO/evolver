from socketIO_client import SocketIO, BaseNamespace
import socketio
import numpy as np
from threading import Thread, Event, Semaphore
import asyncio

evolver_ip = '192.168.1.2'
connected = False
evolver_connection = None
waiting_for_data = True

class EvolverNamespace(BaseNamespace):
    def on_connect(self, *args):
        global connected
        print('Connected eVOLVER')
        connected = True
    def on_disconnect(self, *args):
        global connected
        print('Disconnected eVOLVER')
        connected = False
    def on_reconnect(self, *args):
        global connected
        print('Reconnected eVOLVER')
        connected = True
    def on_dataresponse(self, data):
        global waiting_for_data
        print(data)
        waiting_for_data = False

def send_command(param, message):
    global evolver_connection
    evolver_connection.emit('command', {'param':param, 'message':message})

def set_stir():
    stir = [10] * 16
    #stir = [10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10]
    send_command('stir', stir)

def set_temp():
    temp = [500] * 16
    #temp = [500, 500, 500, 500, 500, 500, 500, 500, 500, 500, 500, 500, 500, 500, 500, 500]
    send_command('temp', temp)
    evolver_connection.emit('data',{})
    
def pump():
    control = np.power(2, range(0, 32))

    #Set which vials desired. range(16) will give [0 ... 15] for all vials
    vials = range(16) # gives [0 ... 15]
    #vials = [1, 5]

    # Creates binary string
    pumps_control = 0
    for vial in vials:
        pumps_control += control[vial]
    pumps_binary = "{0:b}".format(pumps_control)

    # Time to run pumps
    time_to_run = 5

    # If efflux desired for vials in vials list, set to 1. If setting all vials manually using vials list, set to 0.
    run_efflux = 0

    # Optional params
    time_to_run_efflux = 0
    times_to_repeat = 0
    delay_interval = 0

    send_command('pump', {'pump_time':time_to_run, 'efflux_pump_time':time_to_run_efflux, 'delay_interval':delay_interval, 'times_to_repeat':times_to_repeat, 'run_efflux':run_efflux, 'pumps_binary':pumps_binary})

def stop_pumps():
    send_command('pump', 'stop')

def start_background_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()

def run():
    global evolver_connection, evolver_ip
    socketIO = SocketIO(evolver_ip, 8081)
    evolver_connection = socketIO.define(EvolverNamespace, '/dpu-evolver')
    socketIO.wait()

def main():
    global connected, evolver_connection, waiting_for_data
    new_loop_client = asyncio.new_event_loop()
    client_thread = Thread(target = start_background_loop, args = (new_loop_client,))
    client_thread.daemon = True
    client_thread.start()
    new_loop_client.call_soon_threadsafe(run)

    # Wait for connection to be established
    while not connected:
        pass

    # Comment out params not desired to be set
    #set_stir()
    #set_temp()
    #pump()

    # Stop command for pumps
    #stop_pumps()

    evolver_connection.emit('data',{})
    while waiting_for_data:
        pass

if __name__ == '__main__':
    main()
