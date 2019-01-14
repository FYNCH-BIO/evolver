from socketIO_client import SocketIO, BaseNamespace
import socketio
import numpy as np

evolver_ip = '192.168.1.2'
connected = False
evolver_connection = None

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

def main():
    global connected, evolver_connection
    socketIO = SocketIO(evolver_ip, 8081)
    evolver_connection = socketIO.define(EvolverNamespace, '/dpu-evolver')

    # Wait for connection to be established
    while not connected:
        pass

    # Comment out params not desired to be set
    #set_stir()
    #set_temp()
    #pump()

    # Stop command for pumps
    #stop_pumps()

if __name__ == '__main__':
    main()
