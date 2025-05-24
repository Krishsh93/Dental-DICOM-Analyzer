# Deployment Guide

## Backend Deployment

### 1. Prepare for Deployment

The backend is ready for deployment with the following features:
- ✅ CORS configured for flexible origins
- ✅ Environment variable support
- ✅ Production-ready error handling
- ✅ Health check endpoints
- ✅ Security measures (file validation, directory traversal protection)

### 2. Required Environment Variables

Set these environment variables on your hosting platform:

```bash
# Required
ROBOFLOW_API_KEY=your_roboflow_api_key_here

# Optional but recommended
GROQ_API_KEY=your_groq_api_key_here

# Set after deploying frontend
FRONTEND_URL=https://your-frontend-domain.com

# Optional - customize directories
UPLOAD_DIR=uploads
ANNOTATION_DIR=annotations
```

### 3. Recommended Hosting Platforms

**Railway** (Recommended):
1. Connect your GitHub repository
2. Set environment variables in Railway dashboard
3. Railway will auto-deploy from `backend/` folder

**Render**:
1. Connect GitHub repository
2. Set build command: `pip install -r requirements.txt`
3. Set start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Set environment variables

**Heroku**:
1. Add `Procfile` with: `web: uvicorn main:app --host 0.0.0.0 --port $PORT`
2. Set environment variables
3. Deploy via Git or GitHub

### 4. After Backend Deployment

1. Note your backend URL (e.g., `https://your-app.railway.app`)
2. Test the API at: `https://your-app.railway.app/docs`
3. Check health: `https://your-app.railway.app/health`

## Frontend Deployment

### 1. Update Frontend Configuration

Before deploying frontend, update the API base URL in `frontend/src/App.jsx`:

```javascript
// Replace this line:
const API_BASE = 'http://localhost:8000';

// With your deployed backend URL:
const API_BASE = 'https://your-backend-url.railway.app';
```

### 2. Deploy Frontend

**Vercel** (Recommended for Vite/React):
1. Connect GitHub repository
2. Set build command: `npm run build`
3. Set output directory: `dist`
4. Deploy from `frontend/` folder

**Netlify**:
1. Connect GitHub repository
2. Set build command: `npm run build`
3. Set publish directory: `frontend/dist`

### 3. Update Backend CORS

After frontend deployment, update your backend environment variables:

```bash
FRONTEND_URL=https://your-frontend-domain.vercel.app
```

## Complete Deployment Checklist

- [ ] Deploy backend with environment variables
- [ ] Test backend API endpoints
- [ ] Update frontend with backend URL
- [ ] Deploy frontend
- [ ] Update backend with frontend URL
- [ ] Test complete workflow
- [ ] Verify CORS is working correctly

## Testing Deployment

1. Visit your frontend URL
2. Upload a DICOM file
3. Run prediction
4. Generate report
5. Check all features work end-to-end

## Environment Variables Reference

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `ROBOFLOW_API_KEY` | Yes | Your Roboflow API key | `abc123...` |
| `GROQ_API_KEY` | No | Groq LLM API key for reports | `gsk_...` |
| `FRONTEND_URL` | No | Frontend domain for CORS | `https://app.vercel.app` |
| `UPLOAD_DIR` | No | Upload directory name | `uploads` |
| `ANNOTATION_DIR` | No | Annotations directory | `annotations` |
