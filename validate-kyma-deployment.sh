#!/bin/bash

##############################################################################
# Pre-Deployment Validation Script for Slate on Kyma
# Run this before deploying to catch configuration issues
##############################################################################

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

KUBECONFIG_PATH="/Users/D058802/Documents/Projects/kyma/kubeconfig--sapit-sales-dev-camel.yaml"
NAMESPACE="grtest-ns"
VALUES_FILE="./charts/slate/values-grtest.yaml"

print_header() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
}

print_success() { echo -e "${GREEN}✅ $1${NC}"; }
print_error() { echo -e "${RED}❌ $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
print_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }

ERRORS=0

print_header "Pre-Deployment Validation"

# Check kubeconfig
print_info "Checking kubeconfig..."
if [ ! -f "$KUBECONFIG_PATH" ]; then
    print_error "Kubeconfig not found: $KUBECONFIG_PATH"
    ERRORS=$((ERRORS + 1))
else
    export KUBECONFIG="$KUBECONFIG_PATH"
    if kubectl cluster-info &> /dev/null; then
        print_success "Kubeconfig valid and connected"
    else
        print_error "Cannot connect to cluster with kubeconfig"
        ERRORS=$((ERRORS + 1))
    fi
fi

# Check namespace
print_info "Checking namespace..."
if kubectl get namespace "$NAMESPACE" &> /dev/null; then
    print_success "Namespace $NAMESPACE exists"
else
    print_warning "Namespace $NAMESPACE does not exist (will be created)"
fi

# Check values file
print_info "Checking values file..."
if [ ! -f "$VALUES_FILE" ]; then
    print_error "Values file not found: $VALUES_FILE"
    ERRORS=$((ERRORS + 1))
else
    print_success "Values file exists"

    # Check encryption key
    if grep -q 'encryptionKey: ""' "$VALUES_FILE"; then
        print_error "Encryption key not set in $VALUES_FILE"
        print_info "Generate with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
        ERRORS=$((ERRORS + 1))
    else
        print_success "Encryption key configured"
    fi

    # Check XSUAA
    if grep -q 'xsuaaEnabled: "true"' "$VALUES_FILE"; then
        print_success "XSUAA enabled in backend config"
    else
        print_warning "XSUAA not explicitly enabled in backend config"
    fi
fi

# Check Docker images
print_info "Checking Docker images..."
if docker images | grep -q "slate-backend"; then
    print_success "Backend image exists locally"
else
    print_warning "Backend image not found locally (will need to build)"
fi

if docker images | grep -q "slate-frontend"; then
    print_success "Frontend image exists locally"
else
    print_warning "Frontend image not found locally (will need to build)"
fi

# Check Helm chart
print_info "Checking Helm chart..."
if helm lint ./charts/slate --values "$VALUES_FILE" &> /dev/null; then
    print_success "Helm chart is valid"
else
    print_error "Helm chart validation failed"
    print_info "Run: helm lint ./charts/slate --values $VALUES_FILE"
    ERRORS=$((ERRORS + 1))
fi

# Check frontend build
print_info "Checking frontend production build..."
if [ -d "frontend/.next" ]; then
    print_success "Frontend has been built"
else
    print_warning "Frontend not built (run: cd frontend && npm run build)"
fi

# Check backend dependencies
print_info "Checking backend setup..."
if [ -f "backend/data/database.db" ]; then
    print_success "Backend database exists"
else
    print_warning "Backend database not initialized (will be created on first run)"
fi

# Summary
echo ""
print_header "Validation Summary"

if [ $ERRORS -eq 0 ]; then
    print_success "All critical checks passed!"
    print_info "You can proceed with deployment: ./deploy-kyma-grtest.sh"
else
    print_error "Found $ERRORS critical error(s)"
    print_info "Fix the errors above before deploying"
    exit 1
fi

# Show deployment checklist
echo ""
print_header "Deployment Checklist"
echo "1. ✓ Kubeconfig is valid"
echo "2. ✓ Values file is configured"
echo "3. ✓ Encryption key is set"
echo "4. Build Docker images (if needed)"
echo "5. Push images to registry accessible by Kyma"
echo "6. Run: ./deploy-kyma-grtest.sh"
echo ""

# Show expected resources
print_header "Expected Resources After Deployment"
echo "Deployments:"
echo "  - slate-backend (1 replica)"
echo "  - slate-frontend (2 replicas)"
echo "  - slate-approuter (2 replicas)"
echo ""
echo "Services:"
echo "  - slate-backend (ClusterIP:5055)"
echo "  - slate-frontend (ClusterIP:3000)"
echo "  - slate-approuter (ClusterIP:5000)"
echo ""
echo "Storage:"
echo "  - slate-backend-data (5Gi PVC)"
echo ""
echo "XSUAA:"
echo "  - ServiceInstance: slate-xsuaa"
echo "  - ServiceBinding: slate-xsuaa-binding"
echo ""
echo "Ingress:"
echo "  - APIRule: slate-grtest.<cluster-domain>"
echo ""
