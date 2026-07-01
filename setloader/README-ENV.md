# Environment Configuration

This project now uses environment variables for port configuration to prevent port conflicts and make deployment easier.

## Environment Files

### Main Configuration (`.env`)
```bash
# Port Configuration
BACKEND_PORT=8002
FRONTEND_PORT=3002
NEXT_PUBLIC_API_URL=http://localhost:8002
NEXT_PUBLIC_API_SECRET=change-me

# Existing configuration...
SECRET=change-me
# ... other variables
```

### Frontend Configuration (`setlist-helper/.env.local`)
```bash
# Frontend Environment Configuration
NEXT_PUBLIC_API_URL=http://localhost:8002
NEXT_PUBLIC_API_SECRET=change-me
NEXT_PUBLIC_FRONTEND_PORT=3002
```

## Startup Scripts

### Individual Services
```bash
# Start backend only
./start-backend.sh

# Start frontend only  
./start-frontend.sh
```

### Start Everything
```bash
# Start both backend and frontend
./start-all.sh
```

## Port Configuration

- **Backend**: Port 8002 (configurable via `BACKEND_PORT`)
- **Frontend**: Port 3002 (configurable via `FRONTEND_PORT`)

## Benefits

1. **No Port Conflicts**: Ports are defined in environment files
2. **Easy Deployment**: Change ports by updating `.env` file
3. **Consistent Configuration**: Same ports used across all scripts
4. **Environment Isolation**: Different configs for dev/staging/prod

## Usage

1. Update ports in `.env` file if needed
2. Run `./start-all.sh` to start both services
3. Access frontend at `http://localhost:3002`
4. Backend API available at `http://localhost:8002`
