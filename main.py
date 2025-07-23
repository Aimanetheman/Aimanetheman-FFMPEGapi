```python
from flask import Flask, request, jsonify
import subprocess
import os
import tempfile
import requests
from urllib.parse import urlparse
import uuid
import threading
import time

app = Flask(__name__)

# Job storage
jobs = {}

def download_file(url, filename):
    """Download file from Google Drive URL"""
    # Convert Google Drive view URL to direct download
    if 'drive.google.com' in url:
        file_id = url.split('/d/')[1].split('/')[0]
        download_url = f"https://drive.google.com/uc?id={file_id}&export=download"
    else:
        download_url = url
    
    response = requests.get(download_url)
    with open(filename, 'wb') as f:
        f.write(response.content)
    return filename

def generate_video(job_id, audio_urls, image_url, target_duration):
    """Generate video in background"""
    try:
        jobs[job_id]['status'] = 'downloading'
        
        # Create temp directory
        temp_dir = tempfile.mkdtemp()
        
        # Download audio files
        audio_files = []
        for i, url in enumerate(audio_urls):
            audio_file = os.path.join(temp_dir, f"audio_{i}.mp3")
            download_file(url, audio_file)
            audio_files.append(audio_file)
        
        # Download image
        image_file = os.path.join(temp_dir, "image.jpg")
        download_file(image_url, image_file)
        
        jobs[job_id]['status'] = 'processing'
        
        # Concatenate audio files
        concat_file = os.path.join(temp_dir, "concat.txt")
        with open(concat_file, 'w') as f:
            for audio_file in audio_files:
                f.write(f"file '{audio_file}'\n")
        
        combined_audio = os.path.join(temp_dir, "combined.mp3")
        subprocess.run([
            'ffmpeg', '-f', 'concat', '-safe', '0', '-i', concat_file,
            '-c', 'copy', combined_audio
        ], check=True)
        
        # Create video
        output_video = os.path.join(temp_dir, f"video_{job_id}.mp4")
        subprocess.run([
            'ffmpeg', '-loop', '1', '-i', image_file,
            '-i', combined_audio,
            '-c:v', 'libx264', '-c:a', 'aac',
            '-b:a', '192k', '-b:v', '1000k',
            '-pix_fmt', 'yuv420p',
            '-shortest', output_video
        ], check=True)
        
        jobs[job_id]['status'] = 'completed'
        jobs[job_id]['video_path'] = output_video
        
    except Exception as e:
        jobs[job_id]['status'] = 'error'
        jobs[job_id]['error'] = str(e)

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status": "healthy",
        "service": "video-generator-api",
        "active_jobs": len([j for j in jobs.values() if j['status'] == 'processing'])
    })

@app.route('/generate', methods=['POST'])
def generate():
    data = request.json
    
    if not data or 'audioUrls' not in data or 'imageUrl' not in data:
        return jsonify({"error": "Missing required fields"}), 400
    
    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        'status': 'queued',
        'created_at': time.time()
    }
    
    # Start background job
    thread = threading.Thread(
        target=generate_video,
        args=(job_id, data['audioUrls'], data['imageUrl'], data.get('targetDuration', 3600))
    )
    thread.start()
    
    return jsonify({
        "job_id": job_id,
        "status": "queued",
        "message": "Video generation started"
    })

@app.route('/status/<job_id>', methods=['GET'])
def status(job_id):
    if job_id not in jobs:
        return jsonify({"error": "Job not found"}), 404
    
    return jsonify(jobs[job_id])

@app.route('/download/<job_id>', methods=['GET'])
def download(job_id):
    if job_id not in jobs:
        return jsonify({"error": "Job not found"}), 404
    
    job = jobs[job_id]
    if job['status'] != 'completed':
        return jsonify({"error": "Job not completed"}), 400
    
    return send_file(job['video_path'], as_attachment=True)
    ```

if __name__ == '__main__':
    app.run(debug=True)
