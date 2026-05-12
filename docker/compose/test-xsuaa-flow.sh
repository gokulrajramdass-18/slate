#!/bin/bash

echo "🧪 Testing XSUAA Auto-Login Flow"
echo "================================"
echo ""

echo "1️⃣ Checking service status..."
echo ""

# Check backend
if curl -s http://localhost:5055/api/docs > /dev/null; then
    echo "✅ Backend: Running (http://localhost:5055)"
else
    echo "❌ Backend: Not running"
fi

# Check frontend
if curl -s http://localhost:3000 > /dev/null; then
    echo "✅ Frontend: Running (http://localhost:3000)"
else
    echo "❌ Frontend: Not running"
fi

# Check AppRouter
if curl -s http://localhost:5001 > /dev/null; then
    echo "✅ AppRouter: Running (http://localhost:5001)"
else
    echo "❌ AppRouter: Not running"
fi

echo ""
echo "2️⃣ Testing AppRouter redirect..."
echo ""

# Test AppRouter redirect to XSUAA
REDIRECT=$(curl -s -I http://localhost:5001/ | grep -i location | head -1)
if echo "$REDIRECT" | grep -q "authentication.eu10.hana.ondemand.com"; then
    echo "✅ AppRouter redirects to XSUAA login"
    echo "   Redirect URL: ${REDIRECT#*: }"
else
    echo "⚠️  Not redirecting to XSUAA (might have active session)"
fi

echo ""
echo "3️⃣ Next steps:"
echo ""
echo "   Open your browser to: http://localhost:5001"
echo ""
echo "   Expected flow:"
echo "   1. Redirects to XSUAA login"
echo "   2. Enter SAP credentials"
echo "   3. Automatically lands on dashboard"
echo "   4. User auto-created if new"
echo ""
echo "✅ Setup complete!"

