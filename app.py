import os
from flask import Flask, redirect, render_template, request, send_file, send_from_directory, url_for
from datetime import datetime


app = Flask(__name__)

app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MESSAGE_FOLDER'] = 'messages'

messages = []


@app.route('/')
def index():
    files = [{'name': f, 'type': 'file', 'timestamp': datetime.fromtimestamp(os.path.getmtime(os.path.join(app.config['UPLOAD_FOLDER'], f)))} for f in os.listdir(app.config['UPLOAD_FOLDER'])]

    global messages  # 引用全局变量
    message = [{'message': m['message'], 'type': 'message', 'timestamp': m['timestamp']} for m in messages]
    items = files + message
    items.sort(key=lambda x: x['timestamp'], reverse=True)  # 按照时间戳逆序排序
    return render_template('index.html', items=items)


@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return redirect(url_for('index'))

    file = request.files['file']

    if file.filename == '':
        return redirect(url_for('index'))

    file.save(os.path.join(app.config['UPLOAD_FOLDER'], file.filename))
    return redirect(url_for('index'))
    

@app.route('/message', methods=['POST'])
def add_message():
    if 'message' not in request.form:
        return redirect(url_for('index'))
    
    message = request.form['message']
    timestamp = datetime.now()
    messages.append({'message': message, 'type': 'message', 'timestamp': timestamp})

    return redirect(url_for('index'))


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    return send_file(file_path, as_attachment=True)


@app.route('/delete/<filename>', methods=['POST'])
def delete_file(filename):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

    if os.path.exists(file_path):
        os.remove(file_path)

    return redirect(url_for('index'))

@app.route('/delete_message/<timestamp>', methods=['POST'])
def delete_message(timestamp):
    global messages
    timestamp = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S.%f")

    messages = [msg for msg in messages if msg['timestamp'] != timestamp]
    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(debug=True, port=8080)