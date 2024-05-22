import os
from uuid import uuid4
from flask import Flask, redirect, render_template, request, url_for, send_file
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient
import boto3
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

app.config['TEMPLATES_AUTO_RELOAD'] = True

client = MongoClient(os.getenv('MONGODB_DOMAIN'))
db = client['snap']
messages = db['messages']

s3 = boto3.client(
    "s3",
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
)
s3_bucket_name = os.getenv('AWS_BUCKET_NAME')

local_timezone = timezone(timedelta(hours=10))

@app.route('/')
def index():
    messages_list = [{
                'id': str(m['_id']),
                'message': m['message'], 
                'type': 'message', 
                'timestamp': m['uploadDate'] ,
                'batch_id': m['batch_id']} 
                for m in messages.find({'type': 'message'})]

    files = [{
                'id': str(f['_id']),
                'name': f['name'],
                'type': 'file', 
                'timestamp': f['uploadDate'] ,
                'batch_id': f['batch_id']}
                for f in messages.find({'type': 'file'})]
    

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
def upload_it():
    message = request.form.get('message')
    files = request.files.getlist('file')

    timestamp = datetime.now().replace(microsecond=0)  # Ensure local timezone
    batch_id = str(uuid4())

    if message:
        messages.insert_one({
            'message': message,
            'type': 'message',
            'uploadDate': timestamp,
            'batch_id': batch_id
        })

    for file in files:
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            s3.upload_fileobj(file, s3_bucket_name, filename)
            file_url = f"https://s3.{os.getenv('AWS_REGION')}.amazonaws.com/{os.getenv('AWS_BUCKET_NAME')}/{filename}"
            messages.insert_one({
                'name': filename,
                'url': file_url,
                'type': 'file',
                'uploadDate': timestamp,
                'batch_id': batch_id
            })

    return redirect(url_for('index'))


@app.route('/downloads/<filename>')
def download_file(filename):
    try:
        response = s3.get_object(Bucket=s3_bucket_name, Key=filename)
        return send_file(
            response['Body'],
            as_attachment=True,
            download_name=filename
        )
    except s3.exceptions.NoSuchKey:
        return 'File not found', 404

@app.route('/delete_batch/<batch_id>', methods=['POST'])
def delete_batch(batch_id):
    messages.delete_many({'batch_id': batch_id})

    s3_objects = s3.list_objects_v2(Bucket=s3_bucket_name).get('Contents', [])
    for obj in s3_objects:
        try:
            head_obj = s3.head_object(Bucket=s3_bucket_name, Key=obj['Key'])
            metadata = head_obj.get('Metadata', {})
            if metadata.get('batch_id') == batch_id:
                s3.delete_object(Bucket=s3_bucket_name, Key=obj['Key'])
        except Exception as e:
            print(f"Error deleting object {obj['Key']}: {e}")

    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8000)
