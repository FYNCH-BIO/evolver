from socketIO_client import SocketIO, BaseNamespace

evolver_ip = None
evolver_dpu_ns = None

class DpuNamespace(BaseNamespace):
    def on_connect(self, *args):
        print('Connected DPU as client')
        self.emit('ip', {'ip': evolver_ip}) 

    def on_disconnect(self, *args):
        print('Disconnected DPU as client')

    def on_reconnect(self, *args):
        print('Reconnected DPU as client')
        self.emit('ip', {'ip': evolver_ip}) 

def send_data(data):
    global evolver_dpu_ns
    data['ip'] = evolver_ip
    evolver_dpu_ns.emit('evodata', data)

def start_task_loop():
    asyncio.set_event_loop(loop)
    loop.run_forever()        

def run(ip, dpu_ip, dpu_port):
    global evolver_ip, evolver_dpu_ns
    evolver_ip = ip
    socketIO = SocketIO(dpu_ip, dpu_port)
    evolver_dpu_ns = socketIO.define(DpuNamespace, '/evolver-dpu')
    socketIO.wait()
