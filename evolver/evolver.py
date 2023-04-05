#!/usr/local/bin/env python3.6
import yaml
import time
import asyncio
from multi_server import MultiServer
from threading import Thread
import socket
import evolver_server
import os

conf = {}
CONF_FILENAME = 'conf.yml'
CONF_PATH = os.path.realpath(os.path.join(os.getcwd(),os.path.dirname(__file__), CONF_FILENAME))

def start_background_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()

if __name__ == '__main__':
    # need to get our IP
    with open(CONF_PATH, 'r') as ymlfile:
        conf = yaml.safe_load(ymlfile)


    # Set up the server
    server_loop = asyncio.new_event_loop()
    ms = MultiServer(loop=server_loop)
    app1 = ms.add_app(port = conf['port'])
    evolver_server.attach(app1, conf)
    ms.run_all()

    # Set up data broadcasting
    bloop = asyncio.new_event_loop()
    last_time = None
    running = False
    while True:
        current_time = time.time()
        commands_in_queue = evolver_server.get_num_commands() > 0

        if (last_time is None or current_time - last_time > conf['broadcast_timing'] or commands_in_queue) and not running:
            if last_time is None or current_time - last_time > conf['broadcast_timing']:
                last_time = current_time
            try:
                running = True
                bloop.run_until_complete(evolver_server.broadcast(commands_in_queue))
                running = False
            except:
                pass
