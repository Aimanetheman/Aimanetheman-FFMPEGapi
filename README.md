# Video Generator API

Flask API that combines audio files and images into videos using FFmpeg.

## Endpoints

- POST /generate - Start video generation
- GET /status/<job_id> - Check job status  
- GET /download/<job_id> - Download completed video
- GET /health - Health check

## Deploy to Vercel

1. Connect GitHub repository to Vercel
2. Deploy automatically
3. Use in n8n workflow
