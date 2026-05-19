#!/bin/bash
# Configure kubectl for SAP BTP Kyma cluster (sapit-sales-dev-camel)

echo "=========================================="
echo "Configuring kubectl for Kyma Cluster"
echo "=========================================="
echo ""

# Check if kubectl is installed
if ! command -v kubectl &> /dev/null; then
    echo "❌ Error: kubectl is not installed"
    echo "Install it from: https://kubernetes.io/docs/tasks/tools/"
    exit 1
fi

echo "To connect to the SAP BTP Kyma cluster, you need:"
echo "1. The kubeconfig file from SAP BTP Cockpit"
echo ""
echo "Steps to get kubeconfig:"
echo "1. Log in to SAP BTP Cockpit"
echo "2. Navigate to your subaccount"
echo "3. Go to: Kyma Environment → Kyma Dashboard"
echo "4. Click 'Download Kubeconfig' button"
echo "5. Save the file to ~/.kube/kubeconfig-kyma.yaml"
echo ""
echo "Then run:"
echo "  export KUBECONFIG=~/.kube/kubeconfig-kyma.yaml"
echo "  kubectl config use-context <context-name>"
echo "  kubectl config set-context --current --namespace=grtest-ns"
echo ""
echo "Or merge with your existing config:"
echo "  KUBECONFIG=~/.kube/config:~/.kube/kubeconfig-kyma.yaml kubectl config view --flatten > ~/.kube/config-merged"
echo "  mv ~/.kube/config-merged ~/.kube/config"
echo ""
