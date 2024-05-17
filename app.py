import os
from bson import ObjectId
from flask import Flask, redirect, render_template, request, send_file, send_from_directory, url_for
from datetime import datetime
from pymongo import MongoClient
import gridfs


app = Flask(__name__)

app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['UPLOAD_FOLDER'] = 'uploads'

client = MongoClient('mongodb://localhost:27017/')
db = client['snap']
messages = db['messages']
fs = gridfs.GridFS(db)


@app.route('/')
def index():
    files = [{'id': str(f._id), 'name': f.filename, 'type': 'file', 'timestamp': f.upload_date} for f in fs.find()]
    message = [{'id': str(m['_id']), 'message': m['message'], 'type': 'message', 'timestamp': m['uploadDate']} for m in messages.find()]
    items = files + message
    items.sort(key=lambda x: x['timestamp'], reverse=True)
    return render_template('index.html', items=items)


@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return redirect(url_for('index'))

    file = request.files['file']

    if file.filename == '':
        return redirect(url_for('index'))
    
    timestamp = db.command('serverStatus')['localTime']
    fs.put(file, filename=file.filename, uploadDate=timestamp)
    return redirect(url_for('index'))
    

@app.route('/downloads/<filename>')
def download_file(filename):
    file = fs.find_one({'filename': filename})
    if file:
        return send_file(file, as_attachment=True, download_name=filename)
    return 'File not found', 404


@app.route('/delete/<id>', methods=['POST'])
def delete_file(id):
    file = fs.find_one({'_id': ObjectId(id)})
    if file:
        fs.delete(file._id)
    return redirect(url_for('index'))


@app.route('/message', methods=['POST'])
def add_message():
    if 'message' not in request.form:
        return redirect(url_for('index'))
    
    message = request.form['message']
    timestamp = db.command('serverStatus')['localTime']
    messages.insert_one({'message': message, 'type': 'message', 'uploadDate': timestamp})

    return redirect(url_for('index'))


@app.route('/delete_message/<id>', methods=['POST'])
def delete_message(id):
    messages.delete_one({'_id': ObjectId(id)})
    return redirect(url_for('index'))

 


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8000)
    #host='0.0.0.0',
    #192.168.31.113