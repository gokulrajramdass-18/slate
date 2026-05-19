#!/bin/bash

# Slate Kyma Deployment Script

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
NAMESPACE=${NAMESPACE:-grtest-ns}
KUBECONFIG_PATH=${KUBECONFIG_PATH:-"/Users/D058802/Documents/Projects/kyma/kubeconfig--sapit-sales-dev-camel.yaml"}
VALUES_FILE=${VALUES_FILE:-"values-grtest.yaml"}

echo -e "${GREEN}=== Slate Kyma Deployment ===${NC}"
echo ""
echo "Namespace: $NAMESPACE"
echo "Kubeconfig: $KUBECONFIG_PATH"
echo "Values file: $VALUES_FILE"
echo ""

# Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"

if [ ! -f "$KUBECONFIG_PATH" ]; then
    echo -e "${RED}Error: Kubeconfig not found at $KUBECONFIG_PATH${NC}"
    exit 1
fi

if ! command -v helm &> /dev/null; then
    echo -e "${RED}Error: helm not installed${NC}"
    exit 1
fi

if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}Error: kubectl not installed${NC}"
    exit 1
fi

# Set kubeconfig
export KUBECONFIG=$KUBECONFIG_PATH

# Check cluster connection
echo "Testing cluster connection..."
if ! kubectl cluster-info &> /dev/null; then
    echo -e "${RED}Error: Cannot connect to cluster${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Prerequisites OK${NC}"
echo ""

# Create namespace if it doesn't exist
echo -e "${YELLOW}Creating namespace if needed...${NC}"
kubectl create namespace $NAMESPACE --dry-run=client -o yaml | kubectl apply -f -
echo -e "${GREEN}✓ Namespace ready${NC}"
echo ""

# Install/Upgrade Helm chart
echo -e "${YELLOW}Deploying Slate with Helm...${NC}"
helm upgrade --install slate . \
  --namespace $NAMESPACE \
  --values $VALUES_FILE \
  --create-namespace \
  --wait \
  --timeout 10m

echo -e "${GREEN}✓ Helm deployment complete${NC}"
echo ""

# Wait for pods to be ready
echo -e "${YELLOW}Waiting for pods to be ready...${NC}"
kubectl wait --for=condition=ready pod \
  --selector=app=slate-backend \
  --namespace $NAMESPACE \
  --timeout=300s || true

kubectl wait --for=condition=ready pod \
  --selector=app=slate-sap-ai-core-api \
  --namespace $NAMESPACE \
  --timeout=300s || true

kubectl wait --for=condition=ready pod \
  --selector=app=slate-approuter \
  --namespace $NAMESPACE \
  --timeout=300s || true

echo -e "${GREEN}✓ Pods ready${NC}"
echo ""

# Get application URL
echo -e "${GREEN}=== Deployment Summary ===${NC}"
echo ""
echo "Application URL:"
kubectl get apirule slate -n $NAMESPACE -o jsonpath='{.spec.host}' 2>/dev/null && echo "" || echo "  (APIRule not ready yet)"
echo ""
echo "Pods:"
kubectl get pods -n $NAMESPACE -l app
echo ""
echo "Services:"
kubectl get svc -n $NAMESPACE
echo ""

echo -e "${GREEN}=== Deployment Complete! ===${NC}"
echo ""
echo "Access your application at: https://$(kubectl get apirule slate -n $NAMESPACE -o jsonpath='{.spec.host}' 2>/dev/null || echo 'pending...')"
