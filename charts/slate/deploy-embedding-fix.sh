#!/bin/bash
# Deploy SAP AI Core API v1.0.10 with embeddings support to Kyma

set -e

echo "=========================================="
echo "Deploying SAP AI Core Embeddings Fix"
echo "=========================================="
echo ""

# Check if kubectl is configured
if ! kubectl config current-context &> /dev/null; then
    echo "❌ Error: kubectl context not set"
    echo "Please configure kubectl to connect to your Kyma cluster first"
    exit 1
fi

# Check current namespace
CURRENT_NS=$(kubectl config view --minify -o jsonpath='{..namespace}')
if [ "$CURRENT_NS" != "grtest-ns" ]; then
    echo "⚠️  Warning: Current namespace is '$CURRENT_NS', not 'grtest-ns'"
    echo "Setting namespace to grtest-ns..."
    kubectl config set-context --current --namespace=grtest-ns
fi

echo "📦 Current SAP AI Core API version:"
kubectl get deployment slate-sap-ai-core-api -n grtest-ns -o jsonpath='{.spec.template.spec.containers[0].image}' 2>/dev/null || echo "Deployment not found"
echo ""

echo "🚀 Deploying SAP AI Core API v1.0.10..."
helm upgrade slate . -n grtest-ns -f values-grtest.yaml

echo ""
echo "⏳ Waiting for rollout to complete..."
kubectl rollout status deployment/slate-sap-ai-core-api -n grtest-ns --timeout=300s

echo ""
echo "✅ Deployment complete!"
echo ""
echo "📋 New SAP AI Core API version:"
kubectl get deployment slate-sap-ai-core-api -n grtest-ns -o jsonpath='{.spec.template.spec.containers[0].image}'
echo ""
echo ""

echo "=========================================="
echo "Next Steps:"
echo "=========================================="
echo ""
echo "1. Update the embedding model credential:"
echo "   - Go to: https://slate-grtest.c-83567d2.kyma.ondemand.com/settings/api-keys"
echo "   - Find: 'SAP AI Core - text-embedding-3-small-config'"
echo "   - Edit and change model name to: text-embedding-3-large"
echo ""
echo "2. Test embeddings:"
echo "   - Go to Sources page"
echo "   - Click the three dots menu on 'Manus' source"
echo "   - Select 'Regenerate Embeddings'"
echo "   - Wait a few seconds and refresh"
echo "   - Status and Chunks should now show values"
echo ""
echo "3. Or create a new source to test:"
echo "   - Add Source → YouTube"
echo "   - URL: https://www.youtube.com/watch?v=K27diMbCsuw"
echo "   - Embeddings should generate automatically"
echo ""
