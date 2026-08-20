from flask import Flask, Response
import os

app = Flask(__name__)

@app.route('/metrics')
def metrics():
    try:
        with open("/tmp/metrics.txt") as f:
            data = f.read()
    except FileNotFoundError:
        data = "average_temperature 0\ncurrent_temperature 0\n"
    return Response(data, mimetype='text/plain')

app.run(host='0.0.0.0', port=8000)