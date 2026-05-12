#!/bin/bash

echo "🔐 Enabling XSUAA Mode..."

# Add XSUAA_ENABLED to backend .env if not exists
if ! grep -q "XSUAA_ENABLED" backend/.env 2>/dev/null; then
    echo "Adding XSUAA_ENABLED=true to backend/.env"
    echo "" >> backend/.env
    echo "# XSUAA Authentication" >> backend/.env
    echo "XSUAA_ENABLED=true" >> backend/.env
else
    echo "Updating XSUAA_ENABLED in backend/.env"
    sed -i '' 's/XSUAA_ENABLED=.*/XSUAA_ENABLED=true/' backend/.env
fi

echo "✅ XSUAA mode enabled!"
echo ""
echo "📋 Next steps:"
echo "1. Restart backend: cd backend && uvicorn api.main:app --reload --port 5055"
echo "2. Restart frontend: cd frontend && npm run dev"
echo "3. Access via AppRouter: http://localhost:5001"
echo ""
echo "🔄 Or use the startup script: ./start.sh"
