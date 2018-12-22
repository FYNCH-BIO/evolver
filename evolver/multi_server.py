import asyncio
from aiohttp import web


class MultiServer:

    def __init__(self, loop=None):
        self._apps = []
        self.user_supplied_loop = loop is not None
        if loop is None:
            self.loop = asyncio.get_event_loop()
        else:
            self.loop = loop

    def add_app(self, port):
        app = web.Application(loop=self.loop)

        self._apps.append((app, port))

        return app

    @staticmethod
    async def shutdown(app):
        for ws in app['websockets'].values():
            await ws.close()
        app['websockets'].clear()

    def run_all(self):
        try:
            for app in self._apps:
                app[0]['websockets'] = {}
                app[0].on_shutdown.append(MultiServer.shutdown)

                runner = web.AppRunner(app[0])
                self.loop.run_until_complete(runner.setup())

                site = web.TCPSite(runner, 'localhost', app[1])
                self.loop.run_until_complete(site.start())

                names = sorted(str(s.name) for s in runner.sites)
                print("======== Running on {} ========".format(', '.join(names)))

            print("(Press CTRL+C to quit)")
            self.loop.run_forever()

        except KeyboardInterrupt:
            print('Exiting application due to KeyboardInterrupt')
        finally:
            for app in self._apps:
                app[0].shutdown()
