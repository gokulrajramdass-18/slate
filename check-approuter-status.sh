#!/bin/bash
# Quick status check for AppRouter setup

echo "🔍 Checking AppRouter Local Setup Status..."
echo ""

# Check if services are running
echo "📊 Service Status:"
docker-compose -f docker/compose/docker-compose.approuter.yml ps
echo ""

# Check ports
echo "🔌 Port Status:"
echo "  Port 5001 (AppRouter): $(lsof -ti:5001 > /dev/null 2>&1 && echo '✅ In use' || echo '❌ Not in use')"
echo "  Port 5055 (Backend):   $(lsof -ti:5055 > /dev/null 2>&1 && echo '✅ In use' || echo '❌ Not in use')"
echo "  Port 3000 (Frontend):  $(lsof -ti:3000 > /dev/null 2>&1 && echo '✅ In use' || echo '❌ Not in use')"
echo ""

# Check health endpoints
echo "🏥 Health Check:"
if curl -s http://localhost:5001/ > /dev/null 2>&1; then
    echo "  AppRouter (5001):    ✅ Healthy"
else
    echo "  AppRouter (5001):    ❌ Not responding"
fi

if curl -s http://localhost:5055/api/health > /dev/null 2>&1; then
    echo "  Backend (5055):      ✅ Healthy"
else
    echo "  Backend (5055):      ❌ Not responding"
fi

if curl -s http://localhost:3000/ > /dev/null 2>&1; then
    echo "  Frontend (3000):     ✅ Healthy"
else
    echo "  Frontend (3000):     ❌ Not responding"
fi
echo ""

# Check JWT forwarding configuration
echo "🔐 JWT Forwarding Config:"
if [ -f docker/approuter/default-env.json ]; then
    echo "  Backend forwardAuthToken:  $(cat docker/approuter/default-env.json | jq -r '.destinations[] | select(.name=="backend") | .forwardAuthToken')"
    echo "  Frontend forwardAuthToken: $(cat docker/approuter/default-env.json | jq -r '.destinations[] | select(.name=="frontend") | .forwardAuthToken')"
else
    echo "  ❌ default-env.json not found"
fi
echo ""

# Check recent logs for JWT
echo "🔍 Recent Backend Authorization Headers:"
docker logs slate-backend-approuter 2>&1 | grep -i "authorization" | tail -3 || echo "  (No JWT headers found yet - make an API call first)"
echo ""

echo "✅ Setup Status Check Complete!"
echo ""
echo "📝 To access the application:"
echo "   Open: http://localhost:5001"
echo ""
echo "📝 To view logs:"
echo "   docker logs -f slate-approuter"
echo "   docker logs -f slate-backend-approuter"
echo "   docker logs -f slate-frontend-approuter"
