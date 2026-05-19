# Local Development Guide

This guide covers running Slate locally with two different setups:
1. **Standard Development Mode** - Separate backend and frontend servers (native)
2. **XSUAA Local Mode** - AppRouter with backend and frontend in Docker (simulates Kyma deployment)

---

## Standard Development Mode

Best for: Active development, hot reload, debugging

### Prerequisites

- Python 3.11+
- Node.js 20+
- Docker (optional, for supporting services)

### Setup

1. **Install Backend Dependencies**
   ```bash
   cd backend
   pip install -e .
   cd ..
   ```

2. **Install Frontend Dependencies**
   ```bash
   cd frontend
   npm install
   cd ..
   ```

3. **Install SAP AI Core API Dependencies**
   ```bash
   cd sap-ai-core-api
   pip install -r requirements.txt
   cd ..
   ```

4. **Configure Environment**
   ```bash
   cp .env.example .env
   ```

   Edit `.env` and add:
   ```env
   # Encryption key (required)
   OPEN_NOTEBOOK_ENCRYPTION_KEY=your-secret-key-here

   # Database
   DATABASE_TYPE=sqlite
   SQLITE_DB_PATH=./backend/data/database.db

   # API Keys (at least one required)
   OPENAI_API_KEY=sk-...
   # OR
   ANTHROPIC_API_KEY=sk-ant-...

   # SAP AI Core API (for auto-import functionality and embeddings)
   SAP_AI_CORE_AUTH_URL=https://your-tenant.authentication.sap.hana.ondemand.com
   SAP_AI_CORE_CLIENT_ID=sb-...
   SAP_AI_CORE_CLIENT_SECRET=...
   AICORE_BASE_URL=https://api.ai.prod.eu-central-1.aws.ml.hana.ondemand.com
   AICORE_RESOURCE_GROUP=default

   # API Configuration
   API_HOST=127.0.0.1
   API_PORT=5055
   ```

5. **Initialize Database**
   ```bash
   cd backend
   python -m open_notebook.database.async_migrate migrate
   cd ..
   ```
   # OR
   ANTHROPIC_API_KEY=sk-ant-...

   # API Configuration
   API_HOST=127.0.0.1
   API_PORT=5055
   ```

4. **Initialize Database**
   ```bash
   cd backend
   python -m open_notebook.database.async_migrate migrate
   cd ..
   ```

### Start Development Servers

#### Option 1: Using start.sh script (Recommended)
```bash
./start.sh
```

This starts all services:
- SAP AI Core API on http://localhost:5056 (handles chat and embeddings)
- Backend API on http://localhost:5055
- Frontend dev server on http://localhost:3000

#### Option 2: Manual start (separate terminals)

Terminal 1 - SAP AI Core API:
```bash
cd sap-ai-core-api
python main.py
```

Terminal 2 - Backend:
```bash
cd backend
uvicorn api.main:app --reload --port 5055
```

Terminal 3 - Frontend:
```bash
cd frontend
npm run dev
```

### Access the Application

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:5055
- **API Docs**: http://localhost:5055/api/docs
- **SAP AI Core API**: http://localhost:5056

### Default Login

Create your first user via the registration page or use the API:
```bash
curl -X POST http://localhost:5055/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "email": "admin@localhost",
    "password": "admin123",
    "full_name": "Admin User"
  }'
```

### Stop Development Servers

```bash
./stop.sh
```

Or manually stop the processes in each terminal (Ctrl+C)

---

## XSUAA Local Mode (AppRouter)

Best for: Testing XSUAA integration, simulating Kyma deployment locally

This mode runs backend, frontend, and AppRouter in Docker containers, matching the production Kyma architecture.

### Prerequisites

- Docker and Docker Compose
- All standard prerequisites above

### Architecture

```
Browser → AppRouter (port 5001) → Backend API (port 5055)
          ↓ (proxy)
        Frontend (port 3000)
```

**Key Differences from Kyma:**
- In Kyma: Frontend is built and served as static resources by AppRouter
- Locally: Frontend runs as a separate Next.js container for easier development

### Setup

1. **Complete Standard Setup** (steps 1-5 above)

2. **Configure XSUAA Credentials**

   Edit `docker/approuter/default-env.json` with your XSUAA credentials:
   ```json
   {
     "destinations": [
       {
         "name": "backend",
         "url": "http://backend:5055",
         "forwardAuthToken": true,
         "timeout": 600000
       },
       {
         "name": "frontend",
         "url": "http://frontend:3000",
         "forwardAuthToken": false,
         "timeout": 60000
       }
     ],
     "VCAP_SERVICES": {
       "xsuaa": [{
         "credentials": {
           "clientid": "your-client-id",
           "clientsecret": "your-client-secret",
           "url": "https://your-tenant.authentication.eu10.hana.ondemand.com",
           ...
         }
       }]
     }
   }
   ```

3. **Ensure Backend Data Directory Exists**
   ```bash
   mkdir -p backend/data
   chmod 777 backend/data
   ```

### Start XSUAA Mode

#### Option 1: Using start-xsuaa.sh script (Recommended)
```bash
./start-xsuaa.sh
```

This automatically starts all services:
- SAP AI Core API (local process)
- Backend, Frontend, and AppRouter (Docker containers)

#### Option 2: Manual start

Start SAP AI Core API (local process):
```bash
cd sap-ai-core-api
python main.py > ../sap-ai-core-api.log 2>&1 &
cd ..
```

Start Docker services:
```bash
cd docker/compose
docker-compose -f docker-compose.approuter.yml up -d
```

This starts:
- **SAP AI Core API**: http://localhost:5056 (local Python process)
- **Backend**: http://localhost:5055 (Docker container)
- **Frontend**: http://localhost:3000 (Docker container)
- **AppRouter**: http://localhost:5001 (Docker container with XSUAA)

### Access the Application

- **Application**: http://localhost:5001
- **Backend API** (direct): http://localhost:5055
- **Frontend** (direct): http://localhost:3000
- **API Docs**: http://localhost:5055/api/docs

### Authentication Flow

In local AppRouter mode:
1. Access http://localhost:5001
2. AppRouter redirects to XSUAA OAuth login
3. After successful login, AppRouter creates session and proxies requests
4. Backend receives JWT token from AppRouter
5. User auto-created from JWT if not exists

### View Logs

```bash
# Backend logs
docker logs slate-backend-approuter -f

# Frontend logs
docker logs slate-frontend-approuter -f

# AppRouter logs
docker logs slate-approuter -f

# SAP AI Core API logs
tail -f sap-ai-core-api.log

# All Docker logs
cd docker/compose
docker-compose -f docker-compose.approuter.yml logs -f
```

### Stop XSUAA Mode

#### Option 1: Using stop-xsuaa.sh script (Recommended)
```bash
./stop-xsuaa.sh
```

#### Option 2: Manual stop

```bash
# Stop Docker services
cd docker/compose
docker-compose -f docker-compose.approuter.yml down

# Stop SAP AI Core API
kill $(cat ../../.sap-ai-core-api.pid)
```

---

## Development Tips

### Hot Reload

- **Standard Mode**: Both backend and frontend auto-reload on file changes
- **AppRouter Mode**: Backend auto-reloads, frontend requires rebuild + restart

### Database Reset

```bash
rm backend/data/database.db*
cd backend
python -m open_notebook.database.async_migrate migrate
cd ..
```

### API Testing

Use the interactive API docs:
- http://localhost:5055/api/docs (Swagger UI)
- http://localhost:5055/api/redoc (ReDoc)

### Frontend-Only Development

If you only need to work on frontend without backend changes:

```bash
# Use a deployed backend
cd frontend
echo "VITE_API_URL=https://your-backend-url.com/api" > .env.local
npm run dev
```

### Backend-Only Development

```bash
cd backend
uvicorn api.main:app --reload --port 5055

# Test with curl
curl http://localhost:5055/api/health
```

### Environment Variables

**Backend** (`.env` in root):
- `DATABASE_TYPE` - sqlite (default) or postgresql
- `SQLITE_DB_PATH` - Path to SQLite database file
- `OPENAI_API_KEY` - OpenAI API key
- `ANTHROPIC_API_KEY` - Anthropic API key
- `LOG_LEVEL` - DEBUG, INFO, WARNING, ERROR
- `XSUAA_ENABLED` - Enable XSUAA authentication mode

**Frontend** (`VITE_*` in frontend/.env or environment):
- `VITE_API_URL` - Backend API URL (default: http://localhost:5055/api)
- `VITE_XSUAA_ENABLED` - Enable XSUAA mode (true/false)

---

## Troubleshooting

### Port Already in Use

```bash
# Kill processes on ports
lsof -ti:5055 | xargs kill -9  # Backend
lsof -ti:3000 | xargs kill -9  # Frontend
lsof -ti:5001 | xargs kill -9  # AppRouter
```

### Docker Permission Issues

```bash
# Fix backend data directory permissions
chmod 777 backend/data
```

### Database Locked

```bash
# Stop all processes accessing the database
./stop.sh
cd docker/compose
docker-compose -f docker-compose.approuter.yml down

# Remove WAL files
rm backend/data/database.db-wal
rm backend/data/database.db-shm
```

### AppRouter Not Serving Frontend

```bash
# Verify files were copied
docker exec slate-approuter ls -la /app/resources/

# Should see index.html and assets/ directory
# If empty, rebuild and copy frontend files
```

### Backend Database Errors

```bash
# Check database exists
ls -la backend/data/

# Re-run migrations
cd backend
python -m open_notebook.database.async_migrate migrate
cd ..
```

### Frontend Build Errors

```bash
# Clear node_modules and reinstall
cd frontend
rm -rf node_modules package-lock.json
npm install
npm run build
```

---

## SAP AI Core Embeddings (Local Development)

### Overview

When running locally, Slate can generate embeddings for sources using SAP AI Core models. The SAP AI Core API service runs locally and handles authentication with SAP AI Core.

### Architecture

```
Source Added → Backend (localhost:5055) → Detect SAP AI Core Provider
                ↓
         Auto-route to http://localhost:5056
                ↓
         SAP AI Core API (local) → OAuth Token → SAP AI Core API
                ↓
         Embeddings Generated → Stored in SQLite Database
```

### Setup

1. **Configure SAP AI Core Credentials** in `.env`:
   ```env
   SAP_AI_CORE_AUTH_URL=https://your-tenant.authentication.sap.hana.ondemand.com
   SAP_AI_CORE_CLIENT_ID=sb-...
   SAP_AI_CORE_CLIENT_SECRET=...
   AICORE_BASE_URL=https://api.ai.prod.eu-central-1.aws.ml.hana.ondemand.com
   AICORE_RESOURCE_GROUP=default
   ```

2. **Start SAP AI Core API Service**:
   ```bash
   # Using start.sh (recommended)
   ./start.sh
   
   # Or manually
   cd sap-ai-core-api
   python main.py
   ```

3. **Import SAP AI Core Models** in Slate:
   - Go to Settings → API Keys
   - Click "Auto-import SAP AI Core Models"
   - Credentials automatically imported from environment variables

4. **Configure Embedding Model**:
   - Go to Settings → Models
   - Select embedding model: `SAP AI Core - text-embedding-3-large`
   - System will auto-route to `http://localhost:5056`

### How It Works

**Automatic Provider Detection** (same as Kyma):
- Backend detects `sap_ai_core` provider
- Auto-routes to `http://localhost:5056` (local SAP AI Core API)
- Uses default model: `text-embedding-3-large`
- No Authorization header needed for local service

**Background Generation**:
- Embeddings generate automatically when sources are added
- Content is chunked (1500 chars with 150 overlap)
- Progress visible in backend logs

### Testing Embeddings Locally

1. **Add a YouTube Source**:
   ```bash
   # Start services
   ./start.sh
   
   # Open browser
   http://localhost:3000
   
   # Add Source → YouTube
   # URL: https://www.youtube.com/watch?v=K27diMbCsuw
   ```

2. **Check Backend Logs**:
   ```bash
   tail -f backend.log | grep -E "(🔄|✂️|🔢|✅|❌).*embedding"
   
   # Should see:
   # 🔄 Starting embedding generation for source <id>
   # 🔧 Using SAP AI Core: http://localhost:5056 with model: text-embedding-3-large
   # ✂️ Created N chunks
   # 🔢 Generating embedding 1/N
   # ✅ Successfully generated N embeddings
   ```

3. **Check SAP AI Core API Logs**:
   ```bash
   tail -f sap-ai-core-api.log
   
   # Should see POST requests to /embeddings endpoint
   ```

4. **Verify in UI**:
   - Go to Sources page
   - Check Status column (✓ = success)
   - Check Chunks column (number of chunks generated)

### Troubleshooting Embeddings (Local)

#### SAP AI Core API Not Running

**Symptom**: Backend logs show connection errors to `localhost:5056`

**Fix**:
```bash
# Check if service is running
lsof -i:5056

# If not running, start it
cd sap-ai-core-api
python main.py

# Or use start.sh script
./start.sh
```

#### No Embeddings Generated

**Symptom**: Status and Chunks show "-" after adding source

**Check**:
1. **Embedding model configured**:
   ```bash
   # Check backend logs
   tail -f backend.log | grep "embedding model"
   
   # Should NOT see: "No embedding model configured"
   ```

2. **SAP AI Core credentials valid**:
   ```bash
   # Test credentials
   curl http://localhost:5056/discover
   
   # Should return list of available models
   ```

3. **Content extracted**:
   - Sources must have >100 characters to generate embeddings
   - Check source details to verify content exists

#### Test Embeddings Endpoint

```bash
# Test local SAP AI Core API
curl http://localhost:5056/embeddings \
  -H "Content-Type: application/json" \
  -d '{
    "model": "text-embedding-3-large",
    "input": "test content"
  }'

# Should return:
# {
#   "object": "list",
#   "data": [{"object":"embedding","embedding":[...],"index":0}],
#   "model": "text-embedding-3-large",
#   "usage": {"prompt_tokens":2,"total_tokens":2}
# }
```

#### Enable Debug Logging

Add to `.env`:
```env
LOG_LEVEL=DEBUG
```

Restart backend:
```bash
./stop.sh
./start.sh
```

Check logs for detailed embedding generation info:
```bash
tail -f backend.log | grep -i embedding
```

### XSUAA Mode Embeddings

Embeddings work the same way in XSUAA mode:

```bash
# Start XSUAA mode with SAP AI Core API
./start-xsuaa.sh

# SAP AI Core API runs as local process (http://localhost:5056)
# Backend runs in Docker but connects to host network for SAP AI Core API
```

Backend in Docker container connects to SAP AI Core API via:
- **Mac/Windows**: `http://host.docker.internal:5056`
- **Linux**: `http://172.17.0.1:5056`

Check `docker-compose.approuter.yml` for network configuration.

---

## Next Steps

- See [KYMA_DEPLOYMENT.md](./KYMA_DEPLOYMENT.md) for deploying to SAP BTP Kyma Runtime
- See [ARCHITECTURE.md](../../ARCHITECTURE.md) for system architecture details
- See [WORKFLOW_SYSTEM_COMPLETE.md](../workflows/VISUAL_WORKFLOW_SYSTEM_COMPLETE.md) for workflow features

---

## Quick Reference

### Standard Mode (Native)
```bash
# Start
./start.sh

# Access
http://localhost:3000

# Stop
./stop.sh
```

### XSUAA Mode (Docker)
```bash
# Start
./start-xsuaa.sh

# Access
http://localhost:5001

# Stop
./stop-xsuaa.sh
```

### Services Overview

| Service | Standard Mode | XSUAA Mode | Purpose |
|---------|--------------|------------|---------|
| **SAP AI Core API** | http://localhost:5056 (native) | http://localhost:5056 (native) | Model discovery, chat, and embeddings |
| **Backend** | http://localhost:5055 (native) | http://localhost:5055 (Docker) | FastAPI server with database |
| **Frontend** | http://localhost:3000 (native) | http://localhost:3000 (Docker) | Next.js application |
| **AppRouter** | Not used | http://localhost:5001 (Docker) | XSUAA authentication & routing |

### Key Differences

**Standard Mode:**
- ✅ Fast startup and hot reload
- ✅ Easy debugging with native processes
- ✅ Direct access to frontend at port 3000
- ❌ No XSUAA authentication (uses JWT)

**XSUAA Mode:**
- ✅ Matches production Kyma deployment
- ✅ Full XSUAA OAuth 2.0 flow
- ✅ Tests AppRouter routing configuration
- ❌ Slower startup (Docker containers)
- ❌ No hot reload for backend/frontend

---
