# MedGuard AI - Deployment & Running Guide

## ⚡ Quick Start (Local Development)

### Prerequisites
- Python 3.9+
- Node.js 16+
- npm or yarn

### Step 1: Backend Setup

```bash
cd medguard-ai/backend

# Install Python dependencies
pip install -r requirements.txt

# Important: Install Tesseract OCR locally
# macOS:
brew install tesseract

# Ubuntu/Debian:
sudo apt-get install tesseract-ocr

# Windows:
# Download installer: https://github.com/UB-Mannheim/tesseract/wiki

# On Windows, update pytesseract path in image_processor.py if needed:
# pytesseract.pytesseract.pytesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Add your Anthropic API key to .env
# Edit .env and replace: ANTHROPIC_API_KEY=your_actual_key

# Start backend on port 8000
python main.py
```

Visit: http://localhost:8000/api/docs (Swagger UI)

### Step 2: Frontend Setup

```bash
cd medguard-ai/frontend

# Install dependencies
npm install

# Create .env.local
echo "VITE_API_BASE_URL=http://localhost:8000" > .env.local

# Start frontend on port 5173
npm run dev
```

Visit: http://localhost:5173

---

## 🚀 Production Deployment

### Backend - Render.com

1. **Push to GitHub**
```bash
git push origin main
```

2. **Create New Render Service**
- Go to https://render.com
- Click "New +" → "Web Service"
- Connect your GitHub repo
- Select the main branch
- Build command: `pip install -r backend/requirements.txt`
- Start command: `cd backend && uvicorn main:app --host 0.0.0.0 --port 8000`
- Region: Choose closest to you

3. **Add Environment Variables**
```
ANTHROPIC_API_KEY = your_key_here
DEBUG = false
PORT = 8000
```

4. **Important: Install Tesseract on Render**
Add `apt-get update && apt-get install -y tesseract-ocr` to build process

5. **Deploy!**
- Render automatically deploys on push
- API will be at: `https://medguard-backend.onrender.com`

### Frontend - Vercel

1. **Push to GitHub**
```bash
git push origin main
```

2. **Deploy on Vercel**
- Go to https://vercel.com
- Click "Add New..." → "Project"
- Import your GitHub repo
- Framework: Vite
- Root directory: `./frontend`

3. **Environment Variables**
```
VITE_API_BASE_URL = https://medguard-backend.onrender.com
```

4. **Deploy!**
- Vercel automatically deploys on push
- Site will be at: `https://your-project.vercel.app`

---

## 📋 Checklist Before Production

- [ ] Replace dummy Anthropic key with real key
- [ ] Test medicine scanning with real images
- [ ] Test patient safety with real drug data
- [ ] Verify OCR extracts text correctly
- [ ] Check Claude Vision returns complete analyses
- [ ] Test CORS headers work properly
- [ ] Add HTTPS certificate
- [ ] Set up database (if needed)
- [ ] Add authentication (optional)
- [ ] Configure CDN for images (optional)
- [ ] Set up error monitoring (Sentry, etc.)
- [ ] Add rate limiting

---

## 🧪 Testing Endpoints

### Test Medicine Analysis
```bash
# Create a test image (or use an existing one)
# Convert to base64 and test:

curl -X POST http://localhost:8000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "image_base64": "...",
    "mime_type": "image/jpeg"
  }'
```

### Test Patient Safety
```bash
curl -X POST http://localhost:8000/api/patient-safety \
  -H "Content-Type: application/json" \
  -d '{
    "age": 45,
    "allergies": "Penicillin",
    "current_medications": "Metformin",
    "medical_conditions": "Diabetes"
  }'
```

### Test Dashboard
```bash
curl http://localhost:8000/api/dashboard/stats
```

---

## 🔧 Troubleshooting

### "ModuleNotFoundError: No module named 'pytesseract'"
```bash
pip install pytesseract
```

### "tesseract is not installed"
- macOS: `brew install tesseract`
- Ubuntu: `sudo apt-get install tesseract-ocr`
- Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki

### "CORS error in frontend"
- Check CORS origins in `main.py`
- Add your domain to allowed origins
- Default allows localhost:5173

### "ANTHROPIC_API_KEY not found"
- Create `.env` file in `backend/` directory
- Add: `ANTHROPIC_API_KEY=your_real_key`
- Make sure `.env` is NOT in git (check .gitignore)

### Slow OCR extraction
- Reduce image size before OCR
- Use GPU-accelerated Tesseract if available
- Cache identical image results (already implemented)

---

## 📊 Monitoring

### Backend Logs
- Render: View in Render dashboard
- Local: Check console where `python main.py` runs

### Frontend Errors
- Browser console: F12 → Console tab
- Vercel: Check Analytics dashboard

### API Performance
- Render: Check response times in metrics
- Add monitoring tool like Sentry for errors

---

## 💾 Database Setup (Optional)

For production with persistent storage:

```bash
# Install PostgreSQL
# macOS:
brew install postgresql

# Ubuntu:
sudo apt-get install postgresql

# Create database
createdb medguard

# In Render, select PostgreSQL add-on when creating service
```

Then update `main.py` to use SQLAlchemy for persistent storage.

---

## 💬 Support

For issues:
1. Check swagger docs: http://localhost:8000/api/docs
2. Check logs in your terminal
3. Verify API key is correct
4. Ensure Tesseract is installed
5. Check frontend console for errors
