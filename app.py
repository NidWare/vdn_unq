from flask import Flask, render_template, request, send_file, jsonify
from flask_socketio import SocketIO
import os
import shutil
from werkzeug.utils import secure_filename
import uuid
from celery_app import process_video_task
from datetime import datetime, timedelta
import json
import math

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

app.config['MAX_CONTENT_LENGTH'] = 2048 * 1024 * 1024  # 2GB max file size
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['OUTPUT_FOLDER'] = 'output'
app.config['FILE_RETENTION_HOURS'] = 1  # Files older than this will be deleted

# Ensure upload and output directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'mp4', 'mov'}

def cleanup_old_files():
    """Delete files older than FILE_RETENTION_HOURS"""
    cutoff = datetime.now() - timedelta(hours=app.config['FILE_RETENTION_HOURS'])
    
    # Clean up upload directory
    for session_id in os.listdir(app.config['UPLOAD_FOLDER']):
        session_path = os.path.join(app.config['UPLOAD_FOLDER'], session_id)
        try:
            if os.path.getctime(session_path) < cutoff.timestamp():
                shutil.rmtree(session_path, ignore_errors=True)
        except Exception as e:
            print(f"Error cleaning up upload directory {session_path}: {str(e)}")

    # Clean up output directory
    for session_id in os.listdir(app.config['OUTPUT_FOLDER']):
        session_path = os.path.join(app.config['OUTPUT_FOLDER'], session_id)
        try:
            if os.path.getctime(session_path) < cutoff.timestamp():
                shutil.rmtree(session_path, ignore_errors=True)
        except Exception as e:
            print(f"Error cleaning up output directory {session_path}: {str(e)}")

@app.route('/')
def index():
    # Run cleanup on each homepage visit
    cleanup_old_files()
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'video' not in request.files:
        return jsonify({'error': 'No video file provided'}), 400
    
    file = request.files['video']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type. Only MP4 and MOV files are allowed'}), 400

    orientation = request.form.get('orientation', 'horizontal')
    copies = int(request.form.get('copies', '1'))
    
    if copies < 1 or copies > 5:
        return jsonify({'error': 'Number of copies must be between 1 and 5'}), 400

    # Create unique session ID for this upload
    session_id = str(uuid.uuid4())
    session_input_dir = os.path.join(app.config['UPLOAD_FOLDER'], session_id)
    session_output_dir = os.path.join(app.config['OUTPUT_FOLDER'], session_id)
    
    os.makedirs(session_input_dir, exist_ok=True)
    os.makedirs(session_output_dir, exist_ok=True)

    try:
        # Save uploaded file
        filename = secure_filename(file.filename)
        input_path = os.path.join(session_input_dir, filename)
        file.save(input_path)

        # Start async processing
        task = process_video_task.delay(session_input_dir, session_output_dir, copies, orientation)

        return jsonify({
            'success': True,
            'session_id': session_id,
            'task_id': task.id
        })

    except Exception as e:
        # Clean up on error
        shutil.rmtree(session_input_dir, ignore_errors=True)
        shutil.rmtree(session_output_dir, ignore_errors=True)
        return jsonify({'error': str(e)}), 500

@app.route('/task/<task_id>')
def get_task_status(task_id):
    try:
        task = process_video_task.AsyncResult(task_id)
        print(f"[STATUS] Task {task_id} state: {task.state}")
        
        response = {
            'state': task.state,
        }
        
        if task.state == 'PENDING':
            response['status'] = 'Task is pending...'
        elif task.state == 'PROCESSING':
            response['status'] = task.info.get('status', 'Processing video...')
        elif task.state == 'SUCCESS':
            print(f"[STATUS] Task {task_id} success info: {task.info}")
            if task.info is None:
                response['state'] = 'FAILURE'
                response['error'] = 'Task completed but returned no result'
            elif isinstance(task.info, dict) and task.info.get('status') == 'error':
                response['state'] = 'FAILURE'
                response['error'] = task.info.get('error', 'Unknown error occurred')
            else:
                response['result'] = task.info
        elif task.state == 'FAILURE':
            print(f"[STATUS] Task {task_id} failure info: {task.info}")
            response['status'] = str(task.info.get('status', 'Task failed'))
            response['error'] = str(task.info.get('error', task.info))
        else:
            print(f"[STATUS] Task {task_id} unknown state info: {task.info}")
            response['status'] = str(task.info.get('status', 'Unknown state'))
        
        print(f"[STATUS] Sending response: {response}")
        return jsonify(response)
        
    except Exception as e:
        print(f"[STATUS] Error getting task status: {str(e)}")
        return jsonify({
            'state': 'FAILURE',
            'error': f'Error getting task status: {str(e)}'
        })

@app.route('/download/<session_id>/<filename>')
def download_file(session_id, filename):
    try:
        # Secure the filename and create full path
        secure_name = secure_filename(filename)
        file_path = os.path.join(app.config['OUTPUT_FOLDER'], session_id, secure_name)
        
        if not os.path.exists(file_path):
            return jsonify({'error': 'File not found'}), 404

        # Send file for download
        response = send_file(file_path, as_attachment=True)
        
        # Delete files after successful download
        @response.call_on_close
        def cleanup():
            try:
                # Clean up input directory
                input_dir = os.path.join(app.config['UPLOAD_FOLDER'], session_id)
                if os.path.exists(input_dir):
                    shutil.rmtree(input_dir)
                
                # Clean up output directory
                output_dir = os.path.join(app.config['OUTPUT_FOLDER'], session_id)
                if os.path.exists(output_dir):
                    shutil.rmtree(output_dir)
            except Exception as e:
                print(f"Error cleaning up files for session {session_id}: {str(e)}")
        
        return response

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/upload/start', methods=['POST'])
def start_upload():
    try:
        data = request.json
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        filename = data.get('filename')
        if not filename or not allowed_file(filename):
            return jsonify({'error': 'Invalid file type. Only MP4 and MOV files are allowed'}), 400

        # Create unique session ID and directories
        session_id = str(uuid.uuid4())
        session_input_dir = os.path.join(app.config['UPLOAD_FOLDER'], session_id)
        session_output_dir = os.path.join(app.config['OUTPUT_FOLDER'], session_id)
        
        os.makedirs(session_input_dir, exist_ok=True)
        os.makedirs(session_output_dir, exist_ok=True)

        # Create temporary upload directory for chunks
        upload_dir = os.path.join(session_input_dir, 'chunks')
        os.makedirs(upload_dir, exist_ok=True)

        # Store session info
        session_info = {
            'filename': secure_filename(filename),
            'orientation': data.get('orientation', 'horizontal'),
            'copies': int(data.get('copies', 1)),
            'total_chunks': math.ceil(int(data.get('filesize', 0)) / (1024 * 1024))  # 1MB chunks
        }

        # Save session info
        with open(os.path.join(session_input_dir, 'session_info.json'), 'w') as f:
            json.dump(session_info, f)

        return jsonify({'session_id': session_id})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/upload/chunk/<session_id>', methods=['POST'])
def upload_chunk(session_id):
    try:
        if 'chunk' not in request.files:
            return jsonify({'error': 'No chunk provided'}), 400

        chunk = request.files['chunk']
        chunk_number = int(request.form['chunk_number'])
        
        # Get session directory
        session_input_dir = os.path.join(app.config['UPLOAD_FOLDER'], session_id)
        if not os.path.exists(session_input_dir):
            return jsonify({'error': 'Invalid session'}), 400

        # Save chunk
        chunks_dir = os.path.join(session_input_dir, 'chunks')
        chunk_path = os.path.join(chunks_dir, f'chunk_{chunk_number}')
        chunk.save(chunk_path)

        return jsonify({'success': True})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/upload/complete/<session_id>', methods=['POST'])
def complete_upload(session_id):
    try:
        session_input_dir = os.path.join(app.config['UPLOAD_FOLDER'], session_id)
        session_output_dir = os.path.join(app.config['OUTPUT_FOLDER'], session_id)
        chunks_dir = os.path.join(session_input_dir, 'chunks')

        if not os.path.exists(session_input_dir) or not os.path.exists(chunks_dir):
            return jsonify({'error': 'Invalid session'}), 400

        # Load session info
        with open(os.path.join(session_input_dir, 'session_info.json'), 'r') as f:
            session_info = json.load(f)

        # Combine chunks
        output_path = os.path.join(session_input_dir, session_info['filename'])
        with open(output_path, 'wb') as outfile:
            chunk_number = 0
            while True:
                chunk_path = os.path.join(chunks_dir, f'chunk_{chunk_number}')
                if not os.path.exists(chunk_path):
                    break
                with open(chunk_path, 'rb') as chunk_file:
                    outfile.write(chunk_file.read())
                chunk_number += 1

        # Clean up chunks
        shutil.rmtree(chunks_dir)

        # Start async processing
        task = process_video_task.delay(
            session_input_dir, 
            session_output_dir, 
            session_info['copies'], 
            session_info['orientation']
        )

        return jsonify({
            'success': True,
            'task_id': task.id
        })

    except Exception as e:
        # Clean up on error
        shutil.rmtree(session_input_dir, ignore_errors=True)
        shutil.rmtree(session_output_dir, ignore_errors=True)
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000) 