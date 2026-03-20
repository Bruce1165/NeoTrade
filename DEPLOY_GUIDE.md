# GitHub + Render Deployment Guide
# Dashboard 2.0 Permanent Hosting

## Prerequisites
- GitHub account: https://github.com/signup
- Render account: https://render.com (can use GitHub login)

## Step 1: Push to GitHub

```bash
cd ~/.openclaw/workspace-neo/dashboard2/frontend

# Initialize git (if not already)
git init

# Add all files
git add .

# Commit
git commit -m "Dashboard 2.0 - UM Theme"

# Create GitHub repo (via web or gh CLI)
# Then push:
git remote add origin https://github.com/YOUR_USERNAME/neo-dashboard.git
git branch -M main
git push -u origin main
```

## Step 2: Deploy to Render

1. Go to https://dashboard.render.com
2. Click "New +" → "Static Site"
3. Connect GitHub → Select your repo
4. Settings:
   - Name: neo-dashboard
   - Branch: main
   - Build Command: npm install && npm run build
   - Publish Directory: dist
5. Click "Create Static Site"

## Step 3: Get Permanent URL

Render will give you:
```
https://neo-dashboard.onrender.com
```

This URL is permanent and auto-deploys on every git push.

## Backend Connection

The frontend needs to reach your Flask backend. Options:

### Option A: Deploy backend to Render too
- Create Web Service on Render
- Deploy dashboard/app.py
- Update frontend API_BASE to new URL

### Option B: Keep backend local + ngrok
- Frontend on Render
- Backend on localhost:5003
- Use ngrok tunnel for backend API
- Update frontend to use ngrok URL

### Option C: CORS + ngrok hybrid
- Allow CORS on Flask backend
- Frontend calls ngrok backend URL
- Frontend on Render, backend local

## File Locations

Frontend code:
- ~/.openclaw/workspace-neo/dashboard2/frontend/

Backend code:
- ~/.openclaw/workspace-neo/dashboard/app.py

Built files:
- ~/.openclaw/workspace-neo/dashboard2/frontend/dist/

## Notes

- Render free tier: site sleeps after 15 min idle (wakes on request)
- Custom domain: Available on paid plan ($7/month)
- Auto-deploy: Every git push triggers new deploy
