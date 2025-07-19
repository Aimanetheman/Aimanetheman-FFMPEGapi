# Video Generator API

## Upload naar GitHub
1. Maak nieuwe repository op GitHub
2. Upload alle bestanden uit deze folder
3. Commit changes

## Deploy naar Vercel
1. Ga naar vercel.com
2. Import je GitHub repository
3. Deploy automatisch

## API Endpoints
- `POST /upload` - Upload files and generate video
- `GET /status/{job_id}` - Check job status
- `GET /download/{job_id}` - Download video
- `GET /health` - Health check

## Test
Na deployment test met: `https://your-app.vercel.app/health`

