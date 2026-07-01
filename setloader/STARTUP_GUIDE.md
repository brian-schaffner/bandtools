# SetLoader Startup Guide

## Environment Configuration
- **Backend Port**: 8002 (defined in .env)
- **Frontend Port**: 3002 (defined in .env)
- **API URL**: http://localhost:8002
- **Frontend URL**: http://localhost:3002

## Quick Startup Commands

### Option 1: Start Everything (Recommended)
```bash
./start-all.sh
```

### Option 2: Start Services Individually
```bash
# Start backend
./start-backend.sh

# Start frontend (in separate terminal)
./start-frontend.sh
```

### Option 3: Manual Startup
```bash
# Backend
python3 server.py

# Frontend (in separate terminal)
cd setlist-helper && npm run dev
```

## Service URLs
- **Frontend UI**: http://localhost:3002
- **Backend API**: http://localhost:8002
- **Health Check**: http://localhost:8002/health

## Testing
1. Open http://localhost:3002 in browser
2. Upload TKS-1.pdf file
3. Expected results:
   - 59 songs found
   - 59 songs successfully mapped
   - 0 songs need mapping
   - All 59 songs in output file

## Troubleshooting
- If ports are wrong, check .env file
- If services won't start, check logs in logs/ directory
- Backend runs on port 8002, frontend on port 3002
