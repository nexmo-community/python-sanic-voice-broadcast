import os
import nexmo
from pymongo import MongoClient


if __name__ == '__main__':
    db_client = MongoClient('mongodb://localhost:27017/')
    collection = db_client.contactsDatabase.contactsCollection
    nexmo_client = nexmo.Client(
        application_id=os.environ['BROADCAST_APPLICATION_ID'],
        private_key='broadcast.key'
    )

    contact = collection.find_one()

    response = nexmo_client.create_call({
        'to': [{'type': 'phone', 'number': contact['number']}],
        'from': {'type': 'phone', 'number': os.environ['BROADCAST_NUMBER_FROM']},
        'answer_url': ['https://nexmo-broadcast.ngrok.io']
    })

    print(response)
