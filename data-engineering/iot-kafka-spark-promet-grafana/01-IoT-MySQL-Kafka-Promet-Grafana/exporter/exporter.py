from flask import Flask, Response
import mysql.connector

app = Flask(__name__)

@app.route('/metrics')
def metrics():
    db = mysql.connector.connect(user='root', password='root', host='mysql', database='sensors')
    cursor = db.cursor()
    cursor.execute("SELECT temperature FROM readings ORDER BY timestamp DESC LIMIT 1")
    result = cursor.fetchone()
    temp = result[0] if result else 0

    return Response(f"current_temperature {temp}\n", mimetype='text/plain')

app.run(host='0.0.0.0', port=8000)
