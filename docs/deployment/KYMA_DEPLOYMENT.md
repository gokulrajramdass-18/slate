# SAP BTP Kyma Deployment Guide

Complete guide for deploying Slate to SAP BTP Kyma Runtime with XSUAA authentication.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Architecture Overview](#architecture-overview)
3. [Prepare Docker Images](#prepare-docker-images)
4. [Deploy with Helm](#deploy-with-helm)
5. [Access the Application](#access-the-application)
6. [User Management](#user-management)
7. [Troubleshooting](#troubleshooting)
8. [Maintenance](#maintenance)

---

## Prerequisites

### Required Tools

- Docker (for building images)
- kubectl (configured for your Kyma cluster)
- helm 3.x
- Access to SAP BTP Kyma Runtime

### Required Access

- Docker Hub account (or container registry)
- SAP BTP Kyma namespace with permissions:
  - Deploy workloads
  - Create APIRules
  - Create XSUAA service instances

### Cluster Information

Obtain from your SAP BTP administrator:
- **Kubeconfig file**: Path to your Kyma cluster config
- **Namespace**: Your deployment namespace (e.g., `grtest-ns`)
- **Cluster domain**: e.g., `c-83567d2.kyma.ondemand.com`

---

## Architecture Overview

### Deployment Components

```
Internet
  ↓
Kyma APIRule (Ingress)
  ↓
AppRouter (2 replicas)
  ├─→ Static Frontend Files (embedded)
  └─→ Backend API (via destination)
        ↓
      Backend (1 replica)
        ├─→ SQLite Database (persistent volume)
        └─→ SAP AI Core Proxy (for chat/embeddings)
              ↓
            SAP AI Core Proxy (1 replica)
              ↓
            External SAP AI Core API

XSUAA Service (OAuth 2.0)
  ↓
AppRouter + Backend
```

### Key Features

- **No Separate Frontend Container**: Frontend built as static files embedded in AppRouter
- **XSUAA Authentication**: Enterprise SSO via SAP BTP
- **Session Affinity**: Sticky sessions on AppRouter via cookies
- **Persistent Storage**: Database persisted across pod restarts
- **Auto-scaling**: Can scale AppRouter replicas independently
- **SAP AI Core Integration**: Dedicated proxy service for chat and embedding models
  - Isolated Python environment with gen-ai-hub SDK
  - Handles OAuth token management for SAP AI Core
  - Backend routes chat requests to proxy (avoiding direct external API calls)
  - Model discovery via proxy for automatic credential import

---

## Prepare Docker Images

### 1. Build Backend Image

**Important**: Backend must include Docker environment detection for SAP AI Core proxy routing.

```bash
cd /path/to/slate-v1

# Build for linux/amd64 (Kyma requirement)
docker build --platform linux/amd64 \
  -f docker/backend/Dockerfile \
  -t YOUR_REGISTRY/slate-backend:TAG \
  backend/

# Example:
# docker build --platform linux/amd64 \
#   -f docker/backend/Dockerfile \
#   -t gokulraj18/slate-backend:kyma-v1.0.4 \
#   backend/
```

**Key Backend Features for Kyma**:
- Detects container environment via `/.dockerenv` file
- Routes chat requests to internal SAP AI Core proxy service
- Uses `SAP_AI_CORE_API_URL` environment variable (e.g., `http://slate-sap-ai-core-api:5056`)
- Supports model discovery through proxy for auto-import

### 2. Build SAP AI Core Proxy Image

**Critical Component**: The SAP AI Core proxy isolates the gen-ai-hub SDK dependencies and handles OAuth token management.

```bash
cd sap-ai-core-api

# Build proxy service
docker build --platform linux/amd64 \
  -f Dockerfile \
  -t YOUR_REGISTRY/slate-sap-ai-core-api:TAG \
  .

# Example:
# docker build --platform linux/amd64 \
#   -f Dockerfile \
#   -t gokulraj18/slate-sap-ai-core-api:v1.0.1 \
#   .
```

**SAP AI Core Proxy Features**:
- Uses gen-ai-hub SDK for model discovery, chat, and embeddings
- Provides `/health`, `/discover`, `/chat`, and `/embeddings` endpoints
- Handles OAuth authentication with SAP AI Core
- Reads credentials from environment variables
- Supports both streaming and non-streaming chat
- **Embeddings support** (v1.0.10+) for semantic search and RAG

**Version Requirements**:
- **sap-ai-core-api v1.0.10+** - Required for embeddings support
- **backend kyma-v1.0.10+** - Required for auto-configuration and embedding generation

### 3. Build Frontend with XSUAA Mode

**CRITICAL**: Frontend must be built with `VITE_XSUAA_ENABLED=true` for Kyma deployment.

```bash
cd frontend

# Build with XSUAA enabled
VITE_XSUAA_ENABLED=true VITE_API_URL="" npm run build

cd ..
```

### 4. Build AppRouter with Embedded Frontend

**CRITICAL**: Remove any hardcoded `default-env.json` to avoid conflicts with Kyma XSUAA secrets.

```bash
# Ensure default-env.json is NOT in docker/approuter/
rm -f docker/approuter/default-env.json

# Copy frontend build to approuter resources
rm -rf docker/approuter/resources/*
cp -r frontend/dist/* docker/approuter/resources/

# Build approuter image
docker build --platform linux/amd64 \
  -f docker/approuter/Dockerfile \
  -t YOUR_REGISTRY/slate-approuter:TAG \
  docker/approuter/

# Example:
# docker build --platform linux/amd64 \
#   -f docker/approuter/Dockerfile \
#   -t gokulraj18/slate-approuter:kyma-v1.0.7 \
#   docker/approuter/
```

### 5. Push Images to Registry

```bash
# Push all images
docker push YOUR_REGISTRY/slate-backend:TAG
docker push YOUR_REGISTRY/slate-sap-ai-core-api:TAG
docker push YOUR_REGISTRY/slate-approuter:TAG

# Make sure images are publicly accessible or configure imagePullSecrets
```

**Important**: If using Docker Hub, ensure repositories are **public** or configure image pull secrets in Kyma.

---

## Deploy with Helm

### 1. Configure Values File

Create or update `charts/slate/values-production.yaml`:

```yaml
# Namespace
namespace: your-namespace

# Backend configuration
backend:
  replicaCount: 1
  image:
    repository: YOUR_REGISTRY/slate-backend
    tag: TAG
    pullPolicy: Always
  
  # Enable persistent storage for production
  persistence:
    enabled: true
    size: 10Gi
  
  env:
    xsuaaEnabled: "true"

# SAP AI Core Proxy
sapAiCoreApi:
  enabled: true
  replicaCount: 1
  image:
    repository: YOUR_REGISTRY/slate-sap-ai-core-api
    tag: TAG
    pullPolicy: Always
  
  resources:
    limits:
      cpu: 1000m
      memory: 2Gi
    requests:
      cpu: 500m
      memory: 1Gi
  
  # SAP AI Core credentials (stored in secret)
  credentials:
    authUrl: https://YOUR_AUTH_URL.authentication.eu10.hana.ondemand.com
    clientId: YOUR_CLIENT_ID
    clientSecret: YOUR_CLIENT_SECRET
    baseUrl: https://api.ai.prod.REGION.aws.ml.hana.ondemand.com
    resourceGroup: YOUR_RESOURCE_GROUP

# Frontend - DISABLED (embedded in approuter)
frontend:
  enabled: false

# AppRouter with embedded frontend
approuter:
  enabled: true
  replicaCount: 2
  image:
    repository: YOUR_REGISTRY/slate-approuter
    tag: TAG
    pullPolicy: Always
  
  service:
    port: 5001
  
  sessionAffinity:
    enabled: true
    cookieName: SLATE_SESSION_ID

# XSUAA Service configuration
xsuaa:
  enabled: true
  xsappname: slate-your-namespace
  
  scopes:
    - name: "$XSAPPNAME.User"
      description: "Slate user"
    - name: "$XSAPPNAME.Admin"
      description: "Slate administrator"
  
  roleTemplates:
    - name: User
      description: "Slate User"
      scopeReferences:
        - "$XSAPPNAME.User"
    - name: Admin
      description: "Slate Administrator"
      scopeReferences:
        - "$XSAPPNAME.User"
        - "$XSAPPNAME.Admin"
  
  oauth2Configuration:
    redirectUris:
      - "https://slate-your-namespace.*.kyma.ondemand.com/**"
      - "https://slate-your-namespace.<EXACT_CLUSTER_DOMAIN>/**"

# API Rule configuration
apiRule:
  enabled: true
  host: slate-your-namespace
  tls:
    enabled: true

# Destinations for approuter
destinations:
  backend:
    name: slate-backend
    url: http://slate-backend:5055
    forwardAuthToken: true
    timeout: 600000

# xs-app.json routing
xsApp:
  authenticationMethod: route
  sessionTimeout: 480
  welcomeFile: "/index.html"
  
  routes:
    # API routes - require XSUAA authentication
    - source: "^/api/(.*)$"
      target: "/api/$1"
      destination: slate-backend
      authenticationType: xsuaa
      csrfProtection: false
    
    # Static assets - no authentication
    - source: "^/assets/(.*)$"
      localDir: resources
      authenticationType: none
    
    # All other routes - SPA routing with XSUAA
    - source: "^/(.*)$"
      target: "/index.html"
      localDir: resources
      authenticationType: xsuaa
```

**Important Configuration Notes**:

- **sapAiCoreApi.enabled: true** - Required for chat, embeddings, and SAP AI Core model support
- **sapAiCoreApi.credentials** - Stored in Kubernetes secret, used by proxy for OAuth
- **Backend automatically detects** Kubernetes environment and routes to `http://slate-sap-ai-core-api:5056`
- **Proxy handles** all SAP AI Core authentication and SDK dependencies
- **Embeddings auto-generate** when sources (files, URLs, YouTube videos) are added
- **No manual configuration needed** for SAP AI Core provider - backend auto-detects and routes to proxy

### 2. Set Kubeconfig

```bash
export KUBECONFIG=/path/to/your/kubeconfig.yaml
```

### 3. Install with Helm

```bash
# First-time installation
helm install slate ./charts/slate \
  --namespace your-namespace \
  --values ./charts/slate/values-production.yaml \
  --create-namespace

# Upgrade existing deployment
helm upgrade slate ./charts/slate \
  --namespace your-namespace \
  --values ./charts/slate/values-production.yaml
```

### 4. Monitor Deployment

```bash
# Watch pods starting
kubectl get pods -n your-namespace -w

# Check all resources
kubectl get all,apirule,serviceinstance,servicebinding -n your-namespace

# View logs
kubectl logs -f deployment/slate-backend -n your-namespace -c backend
kubectl logs -f deployment/slate-approuter -n your-namespace -c approuter
```

### 5. Wait for XSUAA Service

The XSUAA service instance takes 30-60 seconds to provision:

```bash
# Check service instance status
kubectl get serviceinstance slate-xsuaa -n your-namespace

# Should show STATUS: Created, READY: True

# Check service binding
kubectl get servicebinding slate-xsuaa-binding -n your-namespace

# Should show STATUS: Created, READY: True
```

---

## Access the Application

### Get Application URL

```bash
kubectl get apirule slate -n your-namespace

# Output shows the host, e.g.: slate-your-namespace
# Full URL: https://slate-your-namespace.<cluster-domain>.kyma.ondemand.com
```

Or get the exact URL:

```bash
kubectl get virtualservice -n your-namespace | grep slate

# Shows full domain, e.g.:
# slate-vjjj5  ...  ["slate-your-namespace.c-83567d2.kyma.ondemand.com"]
```

### First Access

1. Open browser to: `https://slate-your-namespace.<cluster-domain>.kyma.ondemand.com`
2. Redirected to SAP BTP login page (XSUAA)
3. Login with your SAP credentials
4. First-time users are automatically created
5. Redirected to Slate dashboard

---

## User Management

### Auto-User Creation

When a user logs in via XSUAA for the first time:
1. Backend extracts user info from JWT token
2. User automatically created with:
   - Username from email prefix
   - Email from JWT
   - Role based on XSUAA scopes
   - Superadmin flag for configured emails (see `backend/api/services/xsuaa_auth_service.py`)

### Assign Roles in BTP Cockpit

Users need role collections assigned in SAP BTP:

1. Navigate to **BTP Cockpit** → Your Subaccount
2. Go to **Security** → **Users**
3. Find your user by email
4. Assign role collection:
   - **Slate Admin** - Full admin access
   - **Slate User** - Standard user access

### Using BTP CLI

```bash
btp login

btp assign security/role-collection "Slate Admin" \
  --to-user your.email@company.com \
  --subaccount <subaccount-id> \
  --create-user-if-missing
```

### Configure Superadmin Users

Edit `backend/api/services/xsuaa_auth_service.py`:

```python
# List of emails that should be superadmins
SUPERADMIN_EMAILS = [
    "admin@company.com",
    "your.email@company.com"
]
```

Rebuild and redeploy backend image.

---

## SAP AI Core Embeddings Setup

### Overview

Slate automatically generates embeddings for sources (files, URLs, YouTube videos) using SAP AI Core embedding models. The system uses a dedicated SAP AI Core proxy service that handles authentication and model invocation.

### Architecture

```
Source Added → Backend → Detect SAP AI Core Provider
                ↓
         Auto-route to http://slate-sap-ai-core-api:5056
                ↓
         SAP AI Core Proxy → OAuth Token → SAP AI Core API
                ↓
         Embeddings Generated → Stored in Database
```

### How It Works

1. **Automatic Provider Detection**: When a source is added, backend checks the configured embedding model provider
2. **Auto-configuration**: If provider is `sap_ai_core`, backend automatically:
   - Routes to internal proxy: `http://slate-sap-ai-core-api:5056`
   - Uses default model: `text-embedding-3-large`
   - Skips authorization headers (not needed for internal service)
3. **Background Generation**: Embeddings generate in background without blocking source creation
4. **Chunking**: Content is split into chunks (1500 chars with 150 overlap)
5. **Storage**: Embeddings stored in `source_embeddings` table for semantic search

### Configuration

**No manual configuration required!** The system auto-detects SAP AI Core provider and routes correctly.

**Default Settings**:
- **Embedding Model**: `text-embedding-3-large`
- **API URL**: `http://slate-sap-ai-core-api:5056` (internal service)
- **Chunk Size**: 1500 characters
- **Chunk Overlap**: 150 characters

### Version Requirements

- **sap-ai-core-api**: v1.0.10 or higher (includes `/embeddings` endpoint)
- **backend**: kyma-v1.0.10 or higher (auto-configuration support)

### Verifying Embeddings

After adding a source:

1. Go to **Sources** page
2. Check the source row for:
   - **Status**: Should show "✓" (success)
   - **Chunks**: Should show number of embedding chunks (e.g., "12")
3. If embeddings failed, check backend logs:
   ```bash
   kubectl logs -f deployment/slate-backend -n your-namespace -c backend
   ```

### Testing Embeddings

1. **Add a YouTube Source**:
   - Go to Sources → Add Source → YouTube
   - URL: `https://www.youtube.com/watch?v=K27diMbCsuw`
   - Embeddings should auto-generate in 5-10 seconds

2. **Add a File Source**:
   - Go to Sources → Add Source → File Upload
   - Upload a PDF or text file
   - Embeddings generate after upload completes

3. **Verify in UI**:
   - Sources page shows Status and Chunks columns
   - Green checkmark = success
   - Number = embedding chunks created

### Troubleshooting Embeddings

#### No Embeddings Generated

**Symptom**: Status and Chunks show "-" after adding source

**Possible Causes**:

1. **Embedding model not configured**:
   ```bash
   # Check backend logs
   kubectl logs deployment/slate-backend -n your-namespace -c backend | grep "embedding model"
   
   # Should NOT see: "No embedding model configured"
   ```
   
   **Fix**: Ensure SAP AI Core credentials are imported in Settings → API Keys

2. **Proxy service not running**:
   ```bash
   # Check proxy pod
   kubectl get pods -n your-namespace | grep sap-ai-core-api
   
   # Should show: slate-sap-ai-core-api-xxx   1/1   Running
   ```
   
   **Fix**: Check proxy logs for errors:
   ```bash
   kubectl logs -f deployment/slate-sap-ai-core-api -n your-namespace
   ```

3. **Content too short**:
   - Embeddings only generate for content >100 characters
   - Check source has actual content extracted

#### Embeddings Failed with Error

**Symptom**: Backend logs show embedding errors

**Common Errors**:

1. **"Request URL is missing protocol"**:
   - **Cause**: Old backend version without auto-configuration
   - **Fix**: Upgrade to backend kyma-v1.0.10+

2. **"Illegal header value"**:
   - **Cause**: Empty API key causing malformed Authorization header
   - **Fix**: Upgrade to backend kyma-v1.0.12+ (skips header when empty)

3. **"Embedding API error: 404"**:
   - **Cause**: Proxy missing `/embeddings` endpoint
   - **Fix**: Upgrade to sap-ai-core-api v1.0.10+

4. **"SAP AI Core embedding error"**:
   - **Cause**: OAuth token expired or credentials invalid
   - **Fix**: Check SAP AI Core credentials in `values-grtest.yaml`

#### Verify Proxy Embeddings Endpoint

```bash
# Port-forward to proxy service
kubectl port-forward -n your-namespace svc/slate-sap-ai-core-api 5056:5056

# Test embeddings endpoint
curl http://localhost:5056/embeddings \
  -H "Content-Type: application/json" \
  -d '{
    "model": "text-embedding-3-large",
    "input": "test content"
  }'

# Should return: {"object":"list","data":[...],"model":"...","usage":{...}}
```

#### Check Embedding Job Logs

```bash
# Filter for embedding-related logs
kubectl logs -f deployment/slate-backend -n your-namespace -c backend | grep -E "(🔄|✂️|🔢|✅|❌).*embedding"

# Look for:
# 🔄 Starting embedding generation for source <id>
# ✂️ Created N chunks
# 🔢 Generating embedding 1/N
# ✅ Successfully generated N embeddings
```

### Advanced Configuration

If you need to customize embedding settings, update backend environment:

```yaml
# charts/slate/values-grtest.yaml
backend:
  env:
    # Embedding model ID (optional - defaults to auto-detected)
    EMBEDDING_MODEL_ID: "your-model-id"
    
    # Chunk settings (optional)
    EMBEDDING_CHUNK_SIZE: "1500"
    EMBEDDING_CHUNK_OVERLAP: "150"
```

Then redeploy:
```bash
helm upgrade slate ./charts/slate -n your-namespace -f values-grtest.yaml
```

---

## Troubleshooting

### Authorization Request Error

**Symptom**: "Authorization Request Error - The request for authorization was invalid"

**Cause**: Redirect URI mismatch between XSUAA config and actual domain

**Fix**:
```bash
# Get exact cluster domain
kubectl get virtualservice -n your-namespace | grep slate

# Update values file with EXACT domain:
xsuaa:
  oauth2Configuration:
    redirectUris:
      - "https://slate-your-namespace.c-EXACT-CLUSTER-ID.kyma.ondemand.com/**"

# Redeploy
helm upgrade slate ./charts/slate \
  --namespace your-namespace \
  --values ./charts/slate/values-production.yaml
```

### AppRouter ImagePullBackOff

**Symptom**: AppRouter pods stuck in `ImagePullBackOff`

**Cause**: Docker Hub repository is private

**Fix Option 1** - Make repository public:
1. Go to Docker Hub → Repository Settings
2. Change visibility to "Public"
3. Pods will auto-retry and succeed

**Fix Option 2** - Add image pull secret:
```bash
kubectl create secret docker-registry dockerhub-secret \
  --docker-server=https://index.docker.io/v1/ \
  --docker-username=YOUR_USERNAME \
  --docker-password=YOUR_PASSWORD \
  -n your-namespace

# Update deployment to use secret
kubectl patch deployment slate-approuter -n your-namespace \
  -p '{"spec":{"template":{"spec":{"imagePullSecrets":[{"name":"dockerhub-secret"}]}}}}'
```

### Wrong Client ID in OAuth Flow

**Symptom**: OAuth shows wrong `client_id` (not matching your xsappname)

**Cause**: Hardcoded `default-env.json` in Docker image

**Fix**:
1. Remove `docker/approuter/default-env.json`
2. Remove line from `docker/approuter/Dockerfile` that copies it
3. Rebuild approuter image without the file
4. Redeploy

### Pods Running but App Returns 404

**Symptom**: Pods show `2/2 Running` but app returns 404

**Cause**: Frontend files not in approuter image

**Verify**:
```bash
kubectl exec -it deployment/slate-approuter -n your-namespace -c approuter -- ls -la /app/resources/

# Should see index.html and assets/ directory
```

**Fix**:
```bash
# Rebuild with frontend files
rm -rf docker/approuter/resources/*
cp -r frontend/dist/* docker/approuter/resources/
docker build --platform linux/amd64 -f docker/approuter/Dockerfile -t YOUR_REGISTRY/slate-approuter:NEW_TAG docker/approuter/
docker push YOUR_REGISTRY/slate-approuter:NEW_TAG

# Update values and redeploy
helm upgrade slate ./charts/slate --namespace your-namespace --values ./charts/slate/values-production.yaml
```

### Database Not Persisting

**Symptom**: Data lost after pod restart

**Cause**: Persistent volume not enabled

**Fix**:
```yaml
# In values file
backend:
  persistence:
    enabled: true
    size: 10Gi
```

Redeploy with updated values.

### XSUAA Service Binding Not Ready

**Symptom**: AppRouter pods can't start, missing XSUAA secret

**Wait**: Service binding can take 30-60 seconds

**Check**:
```bash
# Check service instance
kubectl get serviceinstance slate-xsuaa -n your-namespace -o yaml | grep -A 5 "status:"

# Check binding
kubectl get servicebinding slate-xsuaa-binding -n your-namespace -o yaml | grep -A 5 "status:"

# If stuck in "Blocked" or "Failed" for >5 minutes
kubectl delete servicebinding slate-xsuaa-binding -n your-namespace
kubectl delete serviceinstance slate-xsuaa -n your-namespace

# Redeploy - Helm will recreate them
helm upgrade slate ./charts/slate --namespace your-namespace --values ./charts/slate/values-production.yaml
```

---

## Maintenance

### Update Application

```bash
# 1. Build new images with new tags
docker build --platform linux/amd64 -f docker/backend/Dockerfile -t YOUR_REGISTRY/slate-backend:v1.0.1 backend/
docker build --platform linux/amd64 -f docker/approuter/Dockerfile -t YOUR_REGISTRY/slate-approuter:v1.0.1 docker/approuter/

# 2. Push images
docker push YOUR_REGISTRY/slate-backend:v1.0.1
docker push YOUR_REGISTRY/slate-approuter:v1.0.1

# 3. Update values file with new tags

# 4. Upgrade deployment
helm upgrade slate ./charts/slate --namespace your-namespace --values ./charts/slate/values-production.yaml
```

### Scale AppRouter

```bash
# Scale via Helm values
# Update values file:
approuter:
  replicaCount: 4

# Apply
helm upgrade slate ./charts/slate --namespace your-namespace --values ./charts/slate/values-production.yaml

# Or scale directly
kubectl scale deployment slate-approuter -n your-namespace --replicas=4
```

### View Logs

```bash
# Backend logs
kubectl logs -f deployment/slate-backend -n your-namespace -c backend

# AppRouter logs
kubectl logs -f deployment/slate-approuter -n your-namespace -c approuter

# All pods
kubectl logs -f -l app=slate -n your-namespace

# Specific pod
kubectl logs slate-backend-xxx-yyy -n your-namespace -c backend
```

### Database Backup

```bash
# Get backend pod name
BACKEND_POD=$(kubectl get pod -n your-namespace -l component=backend -o jsonpath='{.items[0].metadata.name}')

# Copy database out
kubectl cp $BACKEND_POD:/app/data/database.db ./database-backup-$(date +%Y%m%d).db -n your-namespace -c backend

# Restore database
kubectl cp ./database-backup.db $BACKEND_POD:/app/data/database.db -n your-namespace -c backend
kubectl rollout restart deployment slate-backend -n your-namespace
```

### Restart Services

```bash
# Restart backend
kubectl rollout restart deployment slate-backend -n your-namespace

# Restart approuter
kubectl rollout restart deployment slate-approuter -n your-namespace

# Restart all
kubectl rollout restart deployment -n your-namespace
```

### Uninstall Application

```bash
# Uninstall Helm release
helm uninstall slate -n your-namespace

# Manually delete XSUAA service (if Helm doesn't clean up)
kubectl delete servicebinding slate-xsuaa-binding -n your-namespace
kubectl delete serviceinstance slate-xsuaa -n your-namespace

# Delete persistent volume claim (if you want to delete data)
kubectl delete pvc slate-backend-data -n your-namespace
```

---

## Production Checklist

Before going to production:

- [ ] **Persistent Volume**: Enabled and sized appropriately
- [ ] **Backup Strategy**: Automated database backups configured
- [ ] **Resource Limits**: Set appropriate CPU/memory limits
- [ ] **Image Tags**: Use specific tags, not `latest`
- [ ] **Image Registry**: Images in private registry with pull secrets
- [ ] **XSUAA Redirect URIs**: Exact cluster domain configured
- [ ] **Role Collections**: Created and assigned in BTP Cockpit
- [ ] **Superadmin Users**: Configured in backend code
- [ ] **API Keys**: Production API keys for OpenAI/Anthropic
- [ ] **Monitoring**: Logs aggregation and monitoring set up
- [ ] **TLS**: APIRule TLS enabled (default in Kyma)
- [ ] **Scaling**: AppRouter scaled to 2+ replicas
- [ ] **Testing**: End-to-end test with real XSUAA login

---

## Additional Resources

- [Helm Chart Documentation](../../charts/README.md)
- [XSUAA Configuration Guide](./KYMA_XSUAA_DEPLOYMENT.md)
- [Local Development Guide](./LOCAL_DEVELOPMENT.md)
- [Architecture Overview](../../ARCHITECTURE.md)
