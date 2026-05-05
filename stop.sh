#!/bin/bash

# Open Notebook - Stop All Services Script
# Stops local services (backend, frontend, hosting) and Docker containers

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}   Open Notebook - Stopping Services   ${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check if running in Docker mode
DOCKER_MODE=false
if [ -f ".docker-mode" ]; then
    DOCKER_MODE=true
    echo -e "${BLUE}Detected Docker deployment mode${NC}"
    echo ""
fi

# Function to stop process by PID file
stop_service() {
    local service_name=$1
    local pid_file=$2

    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if ps -p $pid > /dev/null 2>&1; then
            echo -e "${YELLOW}Stopping $service_name (PID: $pid)...${NC}"
            kill $pid 2>/dev/null || true

            # Wait for process to stop
            for i in {1..10}; do
                if ! ps -p $pid > /dev/null 2>&1; then
                    echo -e "${GREEN}✓ $service_name stopped${NC}"
                    break
                fi
                sleep 1
            done

            # Force kill if still running
            if ps -p $pid > /dev/null 2>&1; then
                echo -e "${YELLOW}Force killing $service_name...${NC}"
                kill -9 $pid 2>/dev/null || true
                sleep 1
                echo -e "${GREEN}✓ $service_name force stopped${NC}"
            fi
        else
            echo -e "${YELLOW}$service_name process (PID: $pid) not running${NC}"
        fi
        rm "$pid_file"
    else
        echo -e "${YELLOW}No PID file found for $service_name${NC}"
    fi
}

# Stop backend
stop_service "Backend" ".backend.pid"

# Stop frontend
stop_service "Frontend" ".frontend.pid"

# Stop hosting server (if running)
stop_service "Hosting" ".hosting.pid"

# Also check for any remaining processes on ports
check_and_kill_port() {
    local port=$1
    local service=$2
    local pid=$(lsof -ti:$port 2>/dev/null)

    if [ ! -z "$pid" ]; then
        echo -e "${YELLOW}Found $service still running on port $port (PID: $pid)${NC}"
        kill -9 $pid 2>/dev/null || true
        echo -e "${GREEN}✓ Killed process on port $port${NC}"
    fi
}

# Load .env to get ports (using Python to handle complex values)
if [ -f ".env" ] && command -v python3 &> /dev/null; then
    eval $(python3 -c "
import sys
import re
try:
    with open('.env', 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                match = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)=(.*)$', line)
                if match:
                    key, value = match.groups()
                    value = value.strip()
                    if (value.startswith('\"') and value.endswith('\"')) or \
                       (value.startswith(\"'\") and value.endswith(\"'\")):
                        value = value[1:-1]
                    value = value.replace('\"', '\\\"')
                    print(f'export {key}=\"{value}\"')
except FileNotFoundError:
    pass
" 2>/dev/null)
fi

API_PORT=${API_PORT:-5055}
FRONTEND_PORT=${FRONTEND_PORT:-3000}
HOSTING_PORT=${HOSTING_PORT:-5056}
MINIO_PORT=${MINIO_PORT:-9000}
LANGFUSE_PORT=${LANGFUSE_PORT:-3001}
LANGFUSE_ENABLED=${LANGFUSE_ENABLED:-false}

# Function to stop specific Docker containers
stop_docker_containers() {
    if ! command -v docker &> /dev/null; then
        return
    fi

    # Stop Open Notebook specific containers (not using docker-compose down)
    echo -e "${BLUE}Stopping Open Notebook containers...${NC}"

    # Stop backend container
    if [ "$(docker ps -q -f name=open-notebook-backend 2>/dev/null)" ]; then
        echo -e "${YELLOW}Stopping backend container...${NC}"
        docker stop open-notebook-backend > /dev/null 2>&1 || true
        echo -e "${GREEN}✓ Backend container stopped${NC}"
    fi

    # Stop frontend container
    if [ "$(docker ps -q -f name=open-notebook-frontend 2>/dev/null)" ]; then
        echo -e "${YELLOW}Stopping frontend container...${NC}"
        docker stop open-notebook-frontend > /dev/null 2>&1 || true
        echo -e "${GREEN}✓ Frontend container stopped${NC}"
    fi

    # Stop hosting container
    if [ "$(docker ps -q -f name=open-notebook-hosting 2>/dev/null)" ]; then
        echo -e "${YELLOW}Stopping hosting container...${NC}"
        docker stop open-notebook-hosting > /dev/null 2>&1 || true
        echo -e "${GREEN}✓ Hosting container stopped${NC}"
    fi

    # Stop MinIO container
    if [ "$(docker ps -q -f name=open-notebook-minio 2>/dev/null)" ]; then
        echo -e "${YELLOW}Stopping MinIO container...${NC}"
        docker stop open-notebook-minio > /dev/null 2>&1 || true
        echo -e "${GREEN}✓ MinIO container stopped${NC}"
    fi

    # Stop Langfuse containers if running
    if [ "$LANGFUSE_ENABLED" = "true" ] || [ "$(docker ps -q -f name=open-notebook-langfuse 2>/dev/null)" ]; then
        echo -e "${YELLOW}Stopping Langfuse containers...${NC}"
        # Stop individual Langfuse containers instead of compose down
        for container in $(docker ps -q -f name=open-notebook-langfuse 2>/dev/null); do
            docker stop $container > /dev/null 2>&1 || true
        done
        echo -e "${GREEN}✓ Langfuse containers stopped${NC}"
    fi
}

# Stop Docker containers if in Docker mode
if [ "$DOCKER_MODE" = "true" ]; then
    stop_docker_containers
    # Remove Docker mode marker
    rm -f .docker-mode
else
    # Local mode - stop individual processes and containers
    check_and_kill_port $API_PORT "Backend"
    check_and_kill_port $FRONTEND_PORT "Frontend"
    check_and_kill_port $HOSTING_PORT "Hosting"
    check_and_kill_port $MINIO_PORT "MinIO"

    # Stop containers in local mode too
    stop_docker_containers
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}     All Services Stopped!             ${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
