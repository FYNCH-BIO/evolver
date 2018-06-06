#!/usr/bin/python
# -*- coding: utf-8 -*-
from socketIO_client import SocketIO, BaseNamespace
import time
from threading import Thread
import asyncio
import blink


class EvolverNamespace(BaseNamespace):

    def on_connect(self, *args):
        print('connected client')

    def on_disconnect(self, *args):
        print('disconnect')

    def on_reconnect(self, *args):
        print('reconnect')

    def on_command(self, *args):
        print('on_evolver_command', args)
        try:
            to_emit = parse_command(args[0])
            if to_emit:
                self.emit('data', {'data': 'test'})
        except TypeError:
            print('Command payload not valid')


def start_background_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()

def parse_command(data):
    if not data['cmd']:
        print('No command found')
        return 0

    print(data['cmd'])
    if data['cmd'] == 'start':
        t.start()
        new_loop.call_soon_threadsafe(blink.run)
        return 1
    elif data['cmd'] == 'stop':
        time.sleep(3)
        blink.stop()
        return 0


if __name__ == '__main__':
    print('Connecting to DPU')
    # Create a new loop
    new_loop = asyncio.new_event_loop()
    # Assign the loop to another thread
    t = Thread(target=start_background_loop, args=(new_loop, ))
    # Start socket
    socketIO = SocketIO('127.0.0.1', 8080)
    evolver_namespace = socketIO.define(EvolverNamespace, '/evolver')
    socketIO.wait()
