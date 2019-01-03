import yaml
import asyncio
from multi_server import MultiServer
from threading import Thread
import socket
import evolver_client
import evolver_server
import os


def start_background_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()

if __name__ == '__main__':

    FLAGS = lambda: None
    # need to get our IP
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    evolver_ip = s.getsockname()[0]
    s.close()

    with open(os.path.realpath(os.path.join(os.getcwd(),os.path.dirname(__file__), 'conf.yml')), 'r') as ymlfile:
        conf = yaml.load(ymlfile)
        for element in conf:
            setattr(FLAGS, element, conf[element])


    # Set up the client: Reaches out to connect to DPU and intiate communications
    new_loop = asyncio.new_event_loop()
    t = Thread(target = start_background_loop, args = (new_loop,))
    t.daemon = True
    t.start()
    new_loop.call_soon_threadsafe(evolver_client.run, evolver_ip, FLAGS.dpu_ip, FLAGS.dpu_port)
    
    # Set up the server
    ms = MultiServer()
    app1 = ms.add_app(port = 8081)
    evolver_server.attach(app1)
    ms.run_all()
