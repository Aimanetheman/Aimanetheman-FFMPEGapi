from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import os
import tempfile
import threading
import uuid
from datetime import datetime
from werkzeug.utils import secure_filename
import subprocess

app = Flask(__name__)
app.config['SECRET_KEY'] = 'video-generator-secret-2024'
CORS(app)

# Store voor actieve jobs
active_jobs = {}

class VideoJob:
    def __init__(self, job_id):
        self.job_id = job_id
        self.status = "queued"
        self.progress = 0
        self.message = "Job queued"
        self.output_path = None
        self.error = None
        self.created_at = datetime.now()

def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'mp3', 'wav', 'aac', 'm4a', 'ogg', 'jpg', 'jpeg', 'png', 'bmp', 'gif'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def combine_audio_files(audio_files, output_path):
    print(f"Combining {len(audio_files)} audio files...")
    concat_file = os.path.join(os.path.dirname(output_path), "concat_list.txt")
    with open(concat_file, 'w') as f:
        for audio_file in audio_files:
            f.write(f"file '{audio_file}'\n")
    
    cmd = ['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', concat_file, '-c', 'copy', output_path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"FFmpeg audio concat failed: {result.stderr}")
    return output_path

def create_video(audio_path, image_path, output_path, target_duration=None):
    print(f"Creating video from {audio_path} and {image_path}")
    
    # Get audio duration
    duration_cmd = ['ffprobe', '-v', 'quiet', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', audio_path]
    result = subprocess.run(duration_cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"Failed to get audio duration: {result.stderr}")
    
    audio_duration = float(result.stdout.strip())
    video_duration = target_duration if target_duration else audio_duration
    
    cmd = [
        'ffmpeg', '-y', '-loop', '1', '-i', image_path, '-i', audio_path,
        '-c:v', 'libx264', '-preset', 'medium', '-crf', '23',
        '-c:a', 'aac', '-b:a', '192k', '-pix_fmt', 'yuv420p',
        '-shortest', '-t', str(video_duration),
        '-vf', 'scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black',
        output_path
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"FFmpeg video creation failed: {result.stderr}")
    return output_path

def run_video_generation(job_id, audio_files, image_file, target_duration, temp_dir):
    job = active_jobs[job_id]
    try:
        job.status = "running"
        job.message = "Starting video generation..."
        job.progress = 10
        
        output_path = os.path.join(temp_dir, f"video_{job_id}.mp4")
        
        job.message = "Combining audio files..."
        job.progress = 30
        combined_audio = os.path.join(temp_dir, "combined_audio.mp3")
        combine_audio_files(audio_files, combined_audio)
        
        job.message = "Creating video..."
        job.progress = 60
        create_video(combined_audio, image_file, output_path, target_duration)
        
        job.status = "completed"
        job.message = "Video generation completed"
        job.progress = 100
        job.output_path = output_path
        
    except Exception as e:
        job.status = "failed"
        job.error = str(e)
        job.message = f"Error: {str(e)}"

@app.route('/')
def home():
    return {
        'status': 'Video Generator API is running!',
        'endpoints': [
            'POST /upload - Upload files and generate video',
            'GET /status/{job_id} - Check job status',
            'GET /download/{job_id} - Download video',
            'GET /health - Health check'
        ]
    }

@app.route('/upload', methods=['POST'])
def upload_and_generate():
    try:
        if 'audio_files' not in request.files or 'image_file' not in request.files:
            return jsonify({'error': 'Missing audio_files or image_file'}), 400
        
        audio_files = request.files.getlist('audio_files')
        image_file = request.files['image_file']
        target_duration = request.form.get('target_duration', type=float)
        
        if not audio_files or audio_files[0].filename == '':
            return jsonify({'error': 'No audio files selected'}), 400
        if image_file.filename == '':
            return jsonify({'error': 'No image file selected'}), 400
        
        for audio_file in audio_files:
            if not allowed_file(audio_file.filename):
                return jsonify({'error': f'Invalid audio file: {audio_file.filename}'}), 400
        if not allowed_file(image_file.filename):
            return jsonify({'error': f'Invalid image file: {image_file.filename}'}), 400
        
        job_id = str(uuid.uuid4())
        job = VideoJob(job_id)
        active_jobs[job_id] = job
        
        temp_dir = tempfile.mkdtemp(prefix=f"video_job_{job_id}_")
        
        saved_audio_files = []
        for i, audio_file in enumerate(audio_files):
            filename = secure_filename(f"audio_{i+1:02d}_{audio_file.filename}")
            filepath = os.path.join(temp_dir, filename)
            audio_file.save(filepath)
            saved_audio_files.append(filepath)
        
        image_filename = secure_filename(f"image_{image_file.filename}")
        image_filepath = os.path.join(temp_dir, image_filename)
        image_file.save(image_filepath)
        
        thread = threading.Thread(target=run_video_generation, args=(job_id, saved_audio_files, image_filepath, target_duration, temp_dir))
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'job_id': job_id,
            'status': 'queued',
            'message': 'Video generation job started',
            'audio_files_count': len(saved_audio_files)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/status/<job_id>')
def get_job_status(job_id):
    if job_id not in active_jobs:
        return jsonify({'error': 'Job not found'}), 404
    
    job = active_jobs[job_id]
    return jsonify({
        'job_id': job_id,
        'status': job.status,
        'progress': job.progress,
        'message': job.message,
        'created_at': job.created_at.isoformat(),
        'error': job.error
    })

@app.route('/download/<job_id>')
def download_video(job_id):
    if job_id not in active_jobs:
        return jsonify({'error': 'Job not found'}), 404
    
    job = active_jobs[job_id]
    if job.status != 'completed':
        return jsonify({'error': 'Video not ready'}), 400
    if not job.output_path or not os.path.exists(job.output_path):
        return jsonify({'error': 'Video file not found'}), 404
    
    return send_file(job.output_path, as_attachment=True, download_name=f'video_{job_id}.mp4', mimetype='video/mp4')

@app.route('/health')
def health_check():
    return jsonify({
        'status': 'healthy',
        'service': 'video-generator-api',
        'active_jobs': len(active_jobs),
        'ffmpeg_available': check_ffmpeg()
    })

def check_ffmpeg():
    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
        return result.returncode == 0
    except:
        return False

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

