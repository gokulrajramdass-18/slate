#!/bin/bash

# Slate - Unified Stop Script
# Stops all Slate services (standard development mode)
# For XSUAA mode, use: ./stop-xsuaa.sh

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}Stopping Slate Application...${NC}"

# Stop SAP AI Core API
if [ -f .sap-ai-core-api.pid ]; then
    PID=$(cat .sap-ai-core-api.pid)
    if kill $PID 2>/dev/null; then
        echo -e "${GREEN}✓ Stopped SAP AI Core API (PID: $PID)${NC}"
    fi
    rm .sap-ai-core-api.pid
fi

# Stop Backend API
if [ -f .backend.pid ]; then
    PID=$(cat .backend.pid)
    if kill $PID 2>/dev/null; then
        echo -e "${GREEN}✓ Stopped Backend API (PID: $PID)${NC}"
    fi
    rm .backend.pid
fi

# Stop Frontend
if [ -f .frontend.pid ]; then
    PID=$(cat .frontend.pid)
    if kill $PID 2>/dev/null; then
        echo -e "${GREEN}✓ Stopped Frontend (PID: $PID)${NC}"
    fi
    rm .frontend.pid
fi

# Kill by port as backup (silent)
lsof -ti:5056 | xargs kill -9 2>/dev/null  # SAP AI Core API
lsof -ti:5055 | xargs kill -9 2>/dev/null  # Backend API
lsof -ti:3000 | xargs kill -9 2>/dev/null  # Frontend

echo -e "${GREEN}All services stopped${NC}"
echo ""
echo -e "${YELLOW}Note: For XSUAA mode (Docker), use: ./stop-xsuaa.sh${NC}"
