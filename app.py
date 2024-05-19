import os
from uuid import uuid4
from bson import ObjectId
from flask import Flask, redirect, render_template, request, send_file, send_from_directory, url_for
from datetime import datetime
from pymongo import MongoClient
import gridfs


app = Flask(__name__)

app.config['TEMPLATES_AUTO_RELOAD'] = True

client = MongoClient('mongodb://localhost:27017/')
db = client['snap']
messages = db['messages']
fs = gridfs.GridFS(db)


@app.route('/')
def index():
    files = [{'id': str(f._id), 'name': f.filename, 'type': 'file', 'timestamp': f.metadata['timestamp'], 'batch_id': f.metadata['batch_id']} for f in fs.find()]
    messages_list = [{'id': str(m['_id']), 'message': m['message'], 'type': 'message', 'timestamp': m['uploadDate'], 'batch_id': m['batch_id']} for m in messages.find()]
    
    items = files + messages_list
    items.sort(key=lambda x: x['timestamp'], reverse=True)
    # Group items by batch_id
    grouped_items = {}
    for item in items:
        batch_id = item['batch_id']
        if batch_id not in grouped_items:
            grouped_items[batch_id] = []
        grouped_items[batch_id].append(item)

    return render_template('index.html', grouped_items=grouped_items)



@app.route('/submit', methods=['POST'])
def send_it():
    message = request.form.get('message')
    files = request.files.getlist('file')  # 使用 getlist 获取多个文件

    timestamp = datetime.now().replace(microsecond=0)
    batch_id = str(uuid4())  # 生成唯一的批次ID

    if message:
        messages.insert_one({
            'message': message,
            'type': 'message',
            'uploadDate': timestamp,
            'batch_id': batch_id
        })

    for file in files:
        if file and file.filename != '':
            fs.put(file, filename=file.filename, metadata={'timestamp': timestamp, 'batch_id': batch_id})

    return redirect(url_for('index'))




# @app.route('/upload', methods=['POST'])
# def upload_file():
#     if 'file' not in request.files:
#         return redirect(url_for('index'))

#     file = request.files['file']

#     if file.filename == '':
#         return redirect(url_for('index'))
    
#     timestamp = db.command('serverStatus')['localTime']
#     fs.put(file, filename=file.filename, uploadDate=timestamp)
#     return redirect(url_for('index'))
    

# @app.route('/message', methods=['POST'])
# def add_message():
#     if 'message' not in request.form:
#         return redirect(url_for('index'))
    
#     message = request.form['message']
#     timestamp = db.command('serverStatus')['localTime']
#     messages.insert_one({'message': message, 'type': 'message', 'uploadDate': timestamp})

#     return redirect(url_for('index'))

@app.route('/downloads/<filename>')
def download_file(filename):
    file = fs.find_one({'filename': filename})
    if file:
        return send_file(file, as_attachment=True, download_name=filename)
    return 'File not found', 404


@app.route('/delete_batch/<batch_id>', methods=['POST'])
def delete_batch(batch_id):
    # Delete messages in the batch
    messages.delete_many({'batch_id': batch_id})

    # Find files in the batch
    files = fs.find({'metadata.batch_id': batch_id})
    for file in files:
        fs.delete(file._id)
    
    return redirect(url_for('index'))


 


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8000)
    #host='0.0.0.0',
    #192.168.31.113