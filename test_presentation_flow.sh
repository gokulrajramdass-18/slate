#!/bin/bash

echo "=== Testing Presentation Generation Flow ==="
echo ""

# Test 1: Check backend is running
echo "1. Testing backend health..."
curl -s http://localhost:5055/health > /dev/null
if [ $? -eq 0 ]; then
    echo "   ✓ Backend is running"
else
    echo "   ✗ Backend is not responding"
    exit 1
fi

# Test 2: Check templates exist
echo "2. Testing templates endpoint..."
TEMPLATES=$(curl -s http://localhost:5055/api/presentations/templates)
if echo "$TEMPLATES" | grep -q "business-pitch"; then
    echo "   ✓ Templates loaded successfully"
    echo "   Templates found: $(echo $TEMPLATES | jq -r '.templates[].id' | tr '\n' ', ')"
else
    echo "   ✗ No templates found"
fi

# Test 3: Create a presentation
echo "3. Creating presentation record..."
CREATE_RESPONSE=$(curl -s -X POST http://localhost:5055/api/presentations/ \
  -H "Content-Type: application/json" \
  -d '{
    "notebook_id": "test-notebook",
    "template_id": "business-pitch",
    "title": "Test Presentation",
    "description": "Testing presentation flow"
  }')

PRESENTATION_ID=$(echo $CREATE_RESPONSE | jq -r '.presentation_id')

if [ "$PRESENTATION_ID" != "null" ] && [ -n "$PRESENTATION_ID" ]; then
    echo "   ✓ Presentation created with ID: $PRESENTATION_ID"
else
    echo "   ✗ Failed to create presentation"
    echo "   Response: $CREATE_RESPONSE"
    exit 1
fi

# Test 4: Generate slides
echo "4. Generating slides..."
GENERATE_RESPONSE=$(curl -s -X POST http://localhost:5055/api/presentations/$PRESENTATION_ID/generate \
  -H "Content-Type: application/json" \
  -d '{
    "template_id": "business-pitch",
    "source_ids": [],
    "user_prompt": "Create a 5-slide presentation about AI trends in 2026",
    "target_slide_count": 5
  }')

if echo "$GENERATE_RESPONSE" | grep -q "success"; then
    SLIDE_COUNT=$(echo $GENERATE_RESPONSE | jq -r '.slide_count')
    echo "   ✓ Generated $SLIDE_COUNT slides"
else
    echo "   ✗ Failed to generate slides"
    echo "   Response: $GENERATE_RESPONSE"
fi

# Test 5: Verify presentation exists in database
echo "5. Verifying presentation in database..."
sqlite3 /Users/D058802/Documents/Projects/slate/slate-v1/backend/data/database.db \
  "SELECT id, title FROM presentations WHERE id = '$PRESENTATION_ID';" > /tmp/pres_check.txt

if grep -q "$PRESENTATION_ID" /tmp/pres_check.txt; then
    echo "   ✓ Presentation found in database"
else
    echo "   ✗ Presentation not found in database"
fi

# Test 6: Check slides
echo "6. Checking generated slides..."
SLIDES_COUNT=$(sqlite3 /Users/D058802/Documents/Projects/slate/slate-v1/backend/data/database.db \
  "SELECT COUNT(*) FROM presentation_content WHERE presentation_id = '$PRESENTATION_ID';")

if [ "$SLIDES_COUNT" -gt 0 ]; then
    echo "   ✓ Found $SLIDES_COUNT slides in database"
else
    echo "   ✗ No slides found in database"
fi

# Test 7: Test GET endpoint
echo "7. Testing GET /api/presentations/{id} endpoint..."
GET_RESPONSE=$(curl -s http://localhost:5055/api/presentations/$PRESENTATION_ID)

if echo "$GET_RESPONSE" | grep -q "title"; then
    echo "   ✓ GET endpoint working"
    echo "   Response: $(echo $GET_RESPONSE | jq -c .)"
else
    echo "   ✗ GET endpoint failed"
    echo "   Response: $GET_RESPONSE"
fi

# Test 8: Test preview endpoint
echo "8. Testing preview endpoint..."
curl -s http://localhost:5055/api/presentations/$PRESENTATION_ID/preview > /tmp/preview.html
if [ -s /tmp/preview.html ]; then
    PREVIEW_SIZE=$(wc -c < /tmp/preview.html)
    echo "   ✓ Preview generated (${PREVIEW_SIZE} bytes)"
else
    echo "   ✗ Preview failed"
fi

echo ""
echo "=== Test Complete ==="
echo "Presentation ID for manual testing: $PRESENTATION_ID"
echo "Preview URL: http://localhost:5055/api/presentations/$PRESENTATION_ID/preview"
