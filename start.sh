#!/bin/bash

# Slate - Unified Startup Script
# Usage: ./start.sh [--xsuaa]
#
# Modes:
#   Default:  Standard development (SAP AI Core API + Backend + Frontend as native processes)
#   --xsuaa:  Docker Compose mode with XSUAA authentication (calls start-xsuaa.sh)

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse arguments
if [ "$1" = "--xsuaa" ]; then
    echo -e "${BLUE}Starting in XSUAA mode (Docker Compose)...${NC}"
    exec ./start-xsuaa.sh
    exit $?
fi

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}   Starting Slate (Development Mode)   ${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Stop any existing processes
echo -e "${YELLOW}Stopping any existing processes...${NC}"
./stop.sh 2>/dev/null
sleep 2

# Belt and braces: free the ports in case stop.sh missed orphaned processes.
for port in 5056 5055 3000; do
    pids=$(lsof -ti tcp:$port 2>/dev/null)
    if [ -n "$pids" ]; then
        echo -e "${YELLOW}Port $port still in use (PIDs: $pids), killing...${NC}"
        kill -9 $pids 2>/dev/null
    fi
done
sleep 1

# Helper: poll a URL until it responds or timeout. Args: url, max_seconds, label
wait_for_http() {
    local url=$1 max=$2 label=$3
    local i=0
    while [ $i -lt $max ]; do
        if curl -s "$url" > /dev/null 2>&1; then
            return 0
        fi
        sleep 1
        i=$((i+1))
    done
    return 1
}

# Start SAP AI Core API
echo -e "${GREEN}[1/3] Starting SAP AI Core API on port 5056...${NC}"
cd sap-ai-core-api
# Prefer the local venv if present (it has gen-ai-hub deps installed)
if [ -x venv/bin/python ]; then
    SAP_PY=venv/bin/python
else
    SAP_PY=python
fi
$SAP_PY main.py > ../sap-ai-core-api.log 2>&1 &
SAP_AI_CORE_PID=$!
echo $SAP_AI_CORE_PID > ../.sap-ai-core-api.pid
cd ..

# Check if SAP AI Core API started (poll up to 30s)
if wait_for_http http://localhost:5056/health 30 "SAP AI Core API"; then
    echo -e "${GREEN}✓ SAP AI Core API started (PID: $SAP_AI_CORE_PID)${NC}"
else
    echo -e "${RED}✗ SAP AI Core API failed to start${NC}"
    echo -e "${YELLOW}Check logs: tail -f sap-ai-core-api.log${NC}"
    tail -20 sap-ai-core-api.log
    exit 1
fi

# Start Backend API
echo -e "${GREEN}[2/3] Starting Backend API on port 5055...${NC}"
cd backend
uvicorn api.main:app --host 0.0.0.0 --port 5055 --reload > ../backend.log 2>&1 &
BACKEND_PID=$!
echo $BACKEND_PID > ../.backend.pid
cd ..

# Check if Backend API started (poll up to 45s — uvicorn cold start can be slow)
if wait_for_http http://localhost:5055/api/health 45 "Backend API"; then
    echo -e "${GREEN}✓ Backend API started (PID: $BACKEND_PID)${NC}"
else
    echo -e "${RED}✗ Backend API failed to start${NC}"
    echo -e "${YELLOW}Check logs: tail -f backend.log${NC}"
    tail -30 backend.log
    exit 1
fi

# Start Frontend (Next.js/React + Vite)
echo -e "${GREEN}[3/3] Starting Frontend on port 3000...${NC}"
cd frontend
npm run dev > ../frontend.log 2>&1 &
FRONTEND_PID=$!
echo $FRONTEND_PID > ../.frontend.pid
cd ..

# Check if Frontend started (poll up to 60s — Next.js dev compile)
if wait_for_http http://localhost:3000 60 "Frontend"; then
    echo -e "${GREEN}✓ Frontend started (PID: $FRONTEND_PID)${NC}"
else
    echo -e "${RED}✗ Frontend failed to start${NC}"
    echo -e "${YELLOW}Check logs: tail -f frontend.log${NC}"
    tail -20 frontend.log
    exit 1
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}   All Services Started Successfully!  ${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}Access Points:${NC}"
echo -e "  Frontend:         ${GREEN}http://localhost:3000${NC}"
echo -e "  Backend API:      ${GREEN}http://localhost:5055${NC}"
echo -e "  API Docs:         ${GREEN}http://localhost:5055/api/docs${NC}"
echo -e "  SAP AI Core API:  ${GREEN}http://localhost:5056${NC}"
echo ""
echo -e "${BLUE}Process IDs:${NC}"
echo -e "  SAP AI Core API:  $SAP_AI_CORE_PID"
echo -e "  Backend API:      $BACKEND_PID"
echo -e "  Frontend:         $FRONTEND_PID"
echo ""
echo -e "${BLUE}Logs:${NC}"
echo -e "  SAP AI Core API:  ${YELLOW}tail -f sap-ai-core-api.log${NC}"
echo -e "  Backend:          ${YELLOW}tail -f backend.log${NC}"
echo -e "  Frontend:         ${YELLOW}tail -f frontend.log${NC}"
echo ""
echo -e "${BLUE}Commands:${NC}"
echo -e "  Stop all:         ${YELLOW}./stop.sh${NC}"
echo -e "  XSUAA mode:       ${YELLOW}./start.sh --xsuaa${NC} (Docker + AppRouter)"
echo ""
echo -e "${YELLOW}Mode: Standard Development (Hot Reload)${NC}"
echo -e "${YELLOW}Authentication: JWT (no XSUAA)${NC}"
echo ""
