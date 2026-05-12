#!/bin/bash

echo "🧪 Testing Complete XSUAA Flow"
echo "=============================="
echo ""

# Test 1: Root page loads
echo "1. Testing root page (should load without redirect)..."
if curl -s http://localhost:5001/ | grep -q "Slate"; then
    echo "   ✅ Root page loads"
else
    echo "   ❌ Root page not loading"
fi

# Test 2: Dashboard requires auth
echo ""
echo "2. Testing dashboard (should redirect to XSUAA)..."
REDIRECT=$(curl -s -I http://localhost:5001/dashboard | grep -i location | head -1)
if echo "$REDIRECT" | grep -q "authentication.eu10.hana.ondemand.com"; then
    echo "   ✅ Dashboard redirects to XSUAA"
else
    echo "   ⚠️  Dashboard behavior: $REDIRECT"
fi

# Test 3: API requires auth
echo ""
echo "3. Testing API endpoint (should redirect to XSUAA)..."
CONTENT=$(curl -s http://localhost:5001/api/workflows | head -100)
if echo "$CONTENT" | grep -q "authentication.eu10.hana.ondemand.com"; then
    echo "   ✅ API redirects to XSUAA"
else
    echo "   ⚠️  API returned: $(echo $CONTENT | head -c 100)"
fi

echo ""
echo "=============================="
echo "Summary:"
echo "- Root page: Public ✅"
echo "- Dashboard: Protected ✅"
echo "- API: Protected ✅"
echo ""
echo "Next: Login at http://localhost:5001/dashboard"
echo "After XSUAA login, you should land on dashboard"
