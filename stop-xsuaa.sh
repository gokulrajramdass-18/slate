#!/bin/bash

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}Stopping Slate XSUAA Mode (Docker)...${NC}"

# Stop SAP AI Core API (local process)
if [ -f .sap-ai-core-api.pid ]; then
    PID=$(cat .sap-ai-core-api.pid)
    if kill $PID 2>/dev/null; then
        echo -e "${GREEN}✓ Stopped SAP AI Core API (PID: $PID)${NC}"
    fi
    rm .sap-ai-core-api.pid
fi

# Kill SAP AI Core API by port as backup
lsof -ti:5056 | xargs kill -9 2>/dev/null

# Stop Docker Compose services
echo -e "${YELLOW}Stopping Docker services...${NC}"
cd docker/compose
docker-compose -f docker-compose.approuter.yml down
cd ../..

echo -e "${GREEN}All services stopped${NC}"
