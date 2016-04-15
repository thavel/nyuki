import aiohttp
import asyncio
import logging
import json

from nyuki import Nyuki


log = logging.getLogger(__name__)


class TestNyuki(Nyuki):

    async def send(self):
        # First get request
        async with aiohttp.request('get', 'http://localhost:5558/message') as r:
            log.info("received response #1: {}".format(r))

        headers = {'content-type': 'application/json'}

        # Post request
        async with aiohttp.request('post', 'http://localhost:5558/message',
                                   data=json.dumps({'message': 'zzzz'}),
                                   headers=headers) as r:
            log.info("received response #2: {}".format(r))

        # Failed request
        try:
            await aiohttp.request('get', 'http://localhost:6000/message')
        except aiohttp.ClientOSError as e:
            log.info("failed to post request: {}".format(e))

    async def setup(self):
        log.info('Sending messages in two seconds')
        await asyncio.sleep(2)
        await self.send()


if __name__ == '__main__':
    n = TestNyuki()
    n.start()
