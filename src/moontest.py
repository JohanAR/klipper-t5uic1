import asyncio
import json
import websockets

class MoonrakerClient:
    def __init__(self):
        self.uri = 'ws://localhost:7125/websocket'
        self.ws = None
        self.connection_lock = asyncio.Lock()
        self.next_id = 0

    async def __connect(self):
        print('trying to connect')
        ws = await websockets.connect(self.uri)
        print('connected')
        return ws

    async def req(self, method):
        async with self.connection_lock:
            if self.ws is None:
                self.ws = await self.__connect()

            req_id = self.next_id
            self.next_id += 1
            req = {'jsonrpc': '2.0', 'method': method, 'id': req_id}
            await self.ws.send(json.dumps(req))

            resp = await self.ws.recv()
            print(f'{resp}')
            return resp

MOON = MoonrakerClient()

async def event_handler():
    while True:
        pass

async def status_refresher():
    while True:
        await MOON.req('printer.info')
        await asyncio.sleep(1)

async def main():
    await asyncio.gather(
            status_refresher(),
            status_refresher(),
            status_refresher()
            )

loop = asyncio.get_event_loop()
refresh_task = loop.create_task(main())
loop.call_later(5, refresh_task.cancel)

try:
    loop.run_until_complete(refresh_task)
except asyncio.CancelledError:
    pass

