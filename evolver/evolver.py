#!/usr/local/bin/env python3.6
import yaml
import time
import asyncio
from multi_server import MultiServer
from threading import Thread
import socket
import evolver_server
import os
import serial


def start_background_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()

if __name__ == '__main__':
    FLAGS = lambda: None
    # need to get our IP
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    evolver_ip = s.getsockname()[0]
    evolver_server.set_ip(evolver_ip)
    s.close()

    with open(os.path.realpath(os.path.join(os.getcwd(),os.path.dirname(__file__), 'conf.yml')), 'r') as ymlfile:
        conf = yaml.load(ymlfile)
        for element in conf:
            setattr(FLAGS, element, conf[element])

    # Set up the server
    server_loop = asyncio.new_event_loop()
    ms = MultiServer(loop=server_loop)
    app1 = ms.add_app(port = 8081)
    evolver_server.attach(app1)
    ms.run_all()

    # Set up data broadcasting
    bloop = asyncio.new_event_loop()
    last_time = None
    while True:
        current_time = time.time() + 20
        if last_time is None or current_time - last_time > 20:
            last_time = current_time
            try:
                bloop.run_until_complete(evolver_server.broadcast())
            except serial.serialutil.SerialException:
                bloop.run_until_complete(evolver_server.broadcast())
                pass
