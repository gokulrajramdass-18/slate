#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting Slate in XSUAA Mode (Docker)...${NC}"
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed${NC}"
    echo -e "${YELLOW}Please install Docker Desktop from: https://docs.docker.com/get-docker/${NC}"
    exit 1
fi

# Check if Docker daemon is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${YELLOW}Docker daemon is not running. Starting Docker Desktop...${NC}"

    # Try to start Docker Desktop on macOS
    if [[ "$OSTYPE" == "darwin"* ]]; then
        if [ -e "/Applications/Docker.app" ]; then
            open -a Docker
            echo -e "${YELLOW}Waiting for Docker Desktop to start (this may take 30-60 seconds)...${NC}"

            # Wait up to 60 seconds for Docker to start
            for i in {1..60}; do
                if docker info > /dev/null 2>&1; then
                    echo -e "${GREEN}✓ Docker Desktop started successfully!${NC}"
                    sleep 2  # Give it a moment to stabilize
                    break
                fi
                if [ $i -eq 60 ]; then
                    echo -e "${RED}✗ Docker Desktop failed to start within 60 seconds${NC}"
                    echo -e "${YELLOW}Please start Docker Desktop manually and run this script again${NC}"
                    exit 1
                fi
                sleep 1
                if [ $((i % 10)) -eq 0 ]; then
                    echo -n "."
                fi
            done
            echo ""
        else
            echo -e "${RED}Error: Docker Desktop not found at /Applications/Docker.app${NC}"
            echo -e "${YELLOW}Please install Docker Desktop from: https://docs.docker.com/get-docker/${NC}"
            exit 1
        fi
    else
        echo -e "${RED}Error: Docker daemon is not running${NC}"
        echo -e "${YELLOW}Please start Docker and run this script again${NC}"
        exit 1
    fi
fi

echo -e "${GREEN}✓ Docker is running${NC}"
echo ""

# Stop any existing processes
echo -e "${YELLOW}Stopping any existing processes...${NC}"
./stop-xsuaa.sh 2>/dev/null
sleep 2

# Start SAP AI Core API (runs locally, not in Docker)
echo -e "${GREEN}Starting SAP AI Core API on port 5056...${NC}"
cd sap-ai-core-api
python main.py > ../sap-ai-core-api.log 2>&1 &
SAP_AI_CORE_PID=$!
echo $SAP_AI_CORE_PID > ../.sap-ai-core-api.pid
cd ..
sleep 4

# Check if SAP AI Core API started
if curl -s http://localhost:5056/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ SAP AI Core API started successfully (PID: $SAP_AI_CORE_PID)${NC}"
else
    echo -e "${RED}✗ SAP AI Core API failed to start${NC}"
    tail -5 sap-ai-core-api.log
    exit 1
fi

# Start Docker Compose services
echo -e "${GREEN}Starting Docker services (backend, frontend, approuter)...${NC}"
cd docker/compose
docker-compose -f docker-compose.approuter.yml up -d

# Wait for services to be healthy
echo -e "${YELLOW}Waiting for services to start...${NC}"
sleep 15

# Check service status
echo -e "${GREEN}Checking service health...${NC}"

# Check Backend
if curl -s http://localhost:5055/api/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Backend API (Docker) is healthy${NC}"
else
    echo -e "${RED}✗ Backend API failed to start${NC}"
    docker logs slate-backend-approuter --tail 20
    exit 1
fi

# Check Frontend
if curl -s http://localhost:3000 > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Frontend (Docker) is healthy${NC}"
else
    echo -e "${RED}✗ Frontend failed to start${NC}"
    docker logs slate-frontend-approuter --tail 20
    exit 1
fi

# Check AppRouter
if curl -s -o /dev/null -w "%{http_code}" http://localhost:5001 | grep -q "302\|200"; then
    echo -e "${GREEN}✓ AppRouter (Docker) is healthy${NC}"
else
    echo -e "${RED}✗ AppRouter failed to start${NC}"
    docker logs slate-approuter --tail 20
    exit 1
fi

cd ../..

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Slate XSUAA Mode Started Successfully!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "Services:"
echo -e "  ${GREEN}✓${NC} SAP AI Core API:  http://localhost:5056 (local process)"
echo -e "  ${GREEN}✓${NC} Backend API:      http://localhost:5055 (Docker)"
echo -e "  ${GREEN}✓${NC} Frontend:         http://localhost:3000 (Docker)"
echo -e "  ${GREEN}✓${NC} AppRouter:        http://localhost:5001 (Docker with XSUAA)"
echo ""
echo -e "View Logs:"
echo -e "  SAP AI Core API:  tail -f sap-ai-core-api.log"
echo -e "  Backend:          docker logs slate-backend-approuter -f"
echo -e "  Frontend:         docker logs slate-frontend-approuter -f"
echo -e "  AppRouter:        docker logs slate-approuter -f"
echo -e "  All Docker logs:  cd docker/compose && docker-compose -f docker-compose.approuter.yml logs -f"
echo ""
echo -e "${YELLOW}Access the application at: http://localhost:5001${NC}"
echo -e "${YELLOW}(AppRouter with XSUAA authentication)${NC}"
echo -e "${YELLOW}To stop all services: ./stop-xsuaa.sh${NC}"
echo ""
