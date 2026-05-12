#!/bin/bash

##############################################################################
# Slate Kyma Deployment Script
# Namespace: grtest-ns
# Cluster: sapit-sales-dev-camel
##############################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
KUBECONFIG_PATH="/Users/D058802/Documents/Projects/kyma/kubeconfig--sapit-sales-dev-camel.yaml"
NAMESPACE="grtest-ns"
RELEASE_NAME="slate"
CHART_PATH="./charts/slate"
VALUES_FILE="./charts/slate/values-grtest.yaml"

# Docker images (update these if using a registry)
BACKEND_IMAGE="slate-backend:latest"
FRONTEND_IMAGE="slate-frontend:latest"

##############################################################################
# Functions
##############################################################################

print_header() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

check_prerequisites() {
    print_header "Checking Prerequisites"

    # Check kubectl
    if ! command -v kubectl &> /dev/null; then
        print_error "kubectl not found. Please install kubectl."
        exit 1
    fi
    print_success "kubectl installed"

    # Check helm
    if ! command -v helm &> /dev/null; then
        print_error "helm not found. Please install Helm 3."
        exit 1
    fi
    print_success "Helm installed"

    # Check docker
    if ! command -v docker &> /dev/null; then
        print_error "docker not found. Please install Docker."
        exit 1
    fi
    print_success "Docker installed"

    # Check kubeconfig
    if [ ! -f "$KUBECONFIG_PATH" ]; then
        print_error "Kubeconfig not found at: $KUBECONFIG_PATH"
        exit 1
    fi
    print_success "Kubeconfig found"

    # Set kubeconfig
    export KUBECONFIG="$KUBECONFIG_PATH"
    print_info "Using kubeconfig: $KUBECONFIG_PATH"

    # Check cluster connection
    if ! kubectl cluster-info &> /dev/null; then
        print_error "Cannot connect to Kubernetes cluster"
        exit 1
    fi
    print_success "Connected to Kubernetes cluster"

    # Check namespace
    if ! kubectl get namespace "$NAMESPACE" &> /dev/null; then
        print_warning "Namespace $NAMESPACE not found. Creating..."
        kubectl create namespace "$NAMESPACE"
        print_success "Namespace $NAMESPACE created"
    else
        print_success "Namespace $NAMESPACE exists"
    fi

    echo ""
}

check_secrets() {
    print_header "Checking Secrets Configuration"

    # Check if encryption key is set in values file
    if grep -q 'encryptionKey: ""' "$VALUES_FILE"; then
        print_error "Encryption key not set in $VALUES_FILE"
        print_info "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""

        read -p "Enter encryption key (or press Enter to generate): " ENCRYPTION_KEY

        if [ -z "$ENCRYPTION_KEY" ]; then
            ENCRYPTION_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
            print_info "Generated encryption key: $ENCRYPTION_KEY"
        fi

        # Update values file
        sed -i.bak "s/encryptionKey: \"\"/encryptionKey: \"$ENCRYPTION_KEY\"/" "$VALUES_FILE"
        print_success "Encryption key set in values file"
    else
        print_success "Encryption key already configured"
    fi

    echo ""
}

build_images() {
    print_header "Building Docker Images"

    print_info "Building backend image..."
    docker build -t "$BACKEND_IMAGE" -f docker/backend/Dockerfile .
    print_success "Backend image built"

    print_info "Building frontend image..."
    # Build production frontend first
    cd frontend
    npm run build
    cd ..
    docker build -t "$FRONTEND_IMAGE" -f docker/frontend/Dockerfile .
    print_success "Frontend image built"

    echo ""
}

push_images() {
    print_header "Pushing Images to Registry"

    print_warning "Images need to be pushed to a container registry accessible by Kyma"
    print_info "Options:"
    print_info "1. Docker Hub: docker tag $BACKEND_IMAGE yourusername/slate-backend:latest"
    print_info "2. SAP Container Registry: Use SAP's internal registry"
    print_info "3. Skip if using local development"

    read -p "Push images to registry? (y/n): " PUSH_IMAGES

    if [ "$PUSH_IMAGES" = "y" ]; then
        read -p "Enter registry (e.g., docker.io/username): " REGISTRY

        print_info "Tagging and pushing backend..."
        docker tag "$BACKEND_IMAGE" "$REGISTRY/slate-backend:latest"
        docker push "$REGISTRY/slate-backend:latest"
        print_success "Backend image pushed"

        print_info "Tagging and pushing frontend..."
        docker tag "$FRONTEND_IMAGE" "$REGISTRY/slate-frontend:latest"
        docker push "$REGISTRY/slate-frontend:latest"
        print_success "Frontend image pushed"

        # Update values file with registry
        sed -i.bak "s|repository: slate-backend|repository: $REGISTRY/slate-backend|" "$VALUES_FILE"
        sed -i.bak "s|repository: slate-frontend|repository: $REGISTRY/slate-frontend|" "$VALUES_FILE"
    else
        print_warning "Skipping image push. Make sure images are accessible by Kyma."
    fi

    echo ""
}

deploy_helm() {
    print_header "Deploying Slate with Helm"

    # Check if release exists
    if helm list -n "$NAMESPACE" | grep -q "$RELEASE_NAME"; then
        print_warning "Release $RELEASE_NAME already exists. Upgrading..."

        helm upgrade "$RELEASE_NAME" "$CHART_PATH" \
            --namespace "$NAMESPACE" \
            --values "$VALUES_FILE" \
            --wait \
            --timeout 10m

        print_success "Helm release upgraded"
    else
        print_info "Installing new Helm release..."

        helm install "$RELEASE_NAME" "$CHART_PATH" \
            --namespace "$NAMESPACE" \
            --values "$VALUES_FILE" \
            --create-namespace \
            --wait \
            --timeout 10m

        print_success "Helm release installed"
    fi

    echo ""
}

verify_deployment() {
    print_header "Verifying Deployment"

    print_info "Waiting for pods to be ready..."
    sleep 10

    # Check pods
    print_info "Checking pods in namespace $NAMESPACE..."
    kubectl get pods -n "$NAMESPACE"
    echo ""

    # Check if all pods are running
    NOT_RUNNING=$(kubectl get pods -n "$NAMESPACE" --field-selector=status.phase!=Running --no-headers 2>/dev/null | wc -l)
    if [ "$NOT_RUNNING" -gt 0 ]; then
        print_warning "$NOT_RUNNING pod(s) not running yet"
        print_info "Check status with: kubectl get pods -n $NAMESPACE"
    else
        print_success "All pods are running"
    fi

    # Check services
    print_info "Checking services..."
    kubectl get svc -n "$NAMESPACE"
    echo ""

    # Check XSUAA service instance
    print_info "Checking XSUAA service instance..."
    kubectl get serviceinstances -n "$NAMESPACE" 2>/dev/null || print_info "No service instances found (may take a moment to appear)"
    echo ""

    # Check API Rule
    print_info "Checking API Rule (Ingress)..."
    kubectl get apirule -n "$NAMESPACE" 2>/dev/null || print_info "No API Rules found"
    echo ""

    # Get application URL
    print_header "Application URL"
    APIRULE_HOST=$(kubectl get apirule -n "$NAMESPACE" -o jsonpath='{.items[0].spec.host}' 2>/dev/null)

    if [ -n "$APIRULE_HOST" ]; then
        print_success "Application URL: https://$APIRULE_HOST"
        print_info "It may take a few minutes for DNS and TLS to propagate"
    else
        print_warning "API Rule not ready yet. Check with: kubectl get apirule -n $NAMESPACE"
    fi

    echo ""
}

show_logs() {
    print_header "Showing Recent Logs"

    read -p "Show logs for which component? (backend/frontend/approuter/skip): " COMPONENT

    case $COMPONENT in
        backend)
            POD=$(kubectl get pods -n "$NAMESPACE" -l app=slate-backend -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
            if [ -n "$POD" ]; then
                kubectl logs -n "$NAMESPACE" "$POD" --tail=50
            else
                print_error "Backend pod not found"
            fi
            ;;
        frontend)
            POD=$(kubectl get pods -n "$NAMESPACE" -l app=slate-frontend -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
            if [ -n "$POD" ]; then
                kubectl logs -n "$NAMESPACE" "$POD" --tail=50
            else
                print_error "Frontend pod not found"
            fi
            ;;
        approuter)
            POD=$(kubectl get pods -n "$NAMESPACE" -l app=slate-approuter -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
            if [ -n "$POD" ]; then
                kubectl logs -n "$NAMESPACE" "$POD" --tail=50
            else
                print_error "AppRouter pod not found"
            fi
            ;;
        skip)
            print_info "Skipping logs"
            ;;
        *)
            print_warning "Invalid component"
            ;;
    esac

    echo ""
}

show_summary() {
    print_header "Deployment Summary"

    echo "Namespace: $NAMESPACE"
    echo "Release: $RELEASE_NAME"
    echo "Kubeconfig: $KUBECONFIG_PATH"
    echo ""

    print_info "Useful commands:"
    echo "  kubectl get pods -n $NAMESPACE"
    echo "  kubectl get svc -n $NAMESPACE"
    echo "  kubectl get apirule -n $NAMESPACE"
    echo "  kubectl logs -n $NAMESPACE <pod-name>"
    echo "  helm list -n $NAMESPACE"
    echo "  helm status $RELEASE_NAME -n $NAMESPACE"
    echo ""

    print_info "To access XSUAA configuration:"
    echo "  kubectl get serviceinstances -n $NAMESPACE"
    echo "  kubectl get servicebindings -n $NAMESPACE"
    echo ""

    print_success "Deployment completed!"
    echo ""
}

##############################################################################
# Main Execution
##############################################################################

main() {
    print_header "Slate Kyma Deployment"
    echo "Namespace: $NAMESPACE"
    echo "Cluster: sapit-sales-dev-camel"
    echo ""

    check_prerequisites
    check_secrets

    read -p "Build and push Docker images? (y/n): " BUILD_IMAGES
    if [ "$BUILD_IMAGES" = "y" ]; then
        build_images
        push_images
    else
        print_warning "Skipping image build. Using existing images."
    fi

    deploy_helm
    verify_deployment
    show_logs
    show_summary
}

# Run main function
main
