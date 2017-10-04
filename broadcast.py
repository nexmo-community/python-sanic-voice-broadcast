import os
import time
import uuid
import jwt
import asyncio
import aiohttp
import aiofiles
import motor.motor_asyncio
import backoff
from logzero import logger


class NexmoRateError(Exception):
    pass


def backoff_exception_handler(details):
    logger.warn(
        f"rate limited backing off for {details['wait']:0.1f} seconds after {details['tries']}"
    )


def backoff_predicate_handler(details):
    logger.warn(
        f"call did not start, backing off for {details['wait']:0.1f} seconds after {details['tries']}"
    )


class BroadcastClient():

    APPLICATION_ID = os.environ['BROADCAST_APPLICATION_ID']
    PRIVATE_KEY_FILE = 'broadcast.key'
    USER_AGENT = 'Nexmo/Demo (Voice Broadcast) v1'
    NUMBER_FROM = os.environ['BROADCAST_NUMBER_FROM']
    NUMBER_TO = None
    ANSWER_URL = 'https://nexmo-broadcast.ngrok.io'

    @classmethod
    async def create(cls, number_to):
        self = cls()
        self.NUMBER_TO = number_to
        async with aiofiles.open(self.PRIVATE_KEY_FILE, mode='r') as key_file:
            self.PRIVATE_KEY = await key_file.read()
        return self

    def get_headers(self):
        iat = int(time.time())
        payload = {
            'iat': iat,
            'application_id': self.APPLICATION_ID,
            'exp': iat + 60,
            'jti': str(uuid.uuid4())
        }

        token = jwt.encode(payload, self.PRIVATE_KEY, algorithm='RS256')

        headers = {
            'User-Agent': self.USER_AGENT,
            'Authorization': 'Bearer ' + token.decode('utf-8')
        }

        return headers

    def get_payload(self):
        return {
            'to': [{'type': 'phone', 'number': self.NUMBER_TO}],
            'from': {'type': 'phone', 'number': self.NUMBER_FROM},
            'answer_url': [self.ANSWER_URL]
        }


@backoff.on_exception(backoff.expo, NexmoRateError, on_backoff=backoff_exception_handler)
@backoff.on_predicate(backoff.fibo, on_backoff=backoff_predicate_handler, max_tries=5)
async def create_call(session, number):
    logger.info(f'calling {number}')

    client = await BroadcastClient.create(number_to=number)
    headers = client.get_headers()
    payload = client.get_payload()

    async with session.post('https://api.nexmo.com/v1/calls', headers=headers, json=payload) as response:
        status = response.status
        nexmo_response = await response.text()

        if status == 429:
            raise NexmoRateError

        logger.info(f'call requested to {number} ({status})')

    return 'started' in nexmo_response


async def broadcast(future, loop):
    client = motor.motor_asyncio.AsyncIOMotorClient('mongodb://localhost:27017')
    contacts_collection = client.contactsDatabase.contactsCollection
    cursor = contacts_collection.find()

    async with aiohttp.ClientSession(loop=loop) as session:
        tasks = [
            create_call(session=session, number=document['number'])
            for document in await cursor.to_list(length=100)
        ]
        await asyncio.gather(*tasks)

    future.set_result(f'attempted to ring {len(tasks)} people')


def run_event_loop():
    loop = asyncio.get_event_loop()
    future = asyncio.Future()

    asyncio.ensure_future(broadcast(future, loop))
    loop.run_until_complete(future)

    logger.debug(future.result())
    loop.close()


if __name__ == '__main__':
    run_event_loop()
