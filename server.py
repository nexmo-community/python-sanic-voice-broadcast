from sanic import Sanic
from sanic.response import json, text
from logzero import logger

app = Sanic()


@app.route("/")
async def answer(request):
    return json([{
        'action': 'talk',
        'text': 'Gotta go fast!'
    }])


@app.route("/events", methods=['POST'])
async def events(request):
    status = request.json['status']

    def log(status):
        if status in ['started', 'ringing']:
            return logger.debug
        elif status in ['answered', 'complete']:
            return logger.info
        elif status in ['machine', 'unanswered', 'busy']:
            return logger.warn
        elif status in ['failed', 'timeout', 'rejected']:
            return logger.error
        else:
            return logger.debug

    log(status)(f'new broadcast event with status: {status}')

    return text(f'POST request - {request.json}')

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
