#!/bin/bash
BASE_URL="http://localhost:5055"
USER_ID="test-user"

echo "Testing public gallery workflow with approval..."
echo ""

# 1. Get a public template with approval
echo "1. Finding Approval Workflow Template..."
TEMPLATE_ID=$(curl -s "$BASE_URL/api/workflow-templates/public" -H "X-User-ID: $USER_ID" | jq -r '.[] | select(.name | contains("Approval")) | .id' | head -1)
echo "Template ID: $TEMPLATE_ID"
echo ""

# 2. Execute the template
echo "2. Executing template..."
EXEC_RESPONSE=$(curl -s -X POST "$BASE_URL/api/workflow-templates/$TEMPLATE_ID/execute" \
  -H "Content-Type: application/json" \
  -H "X-User-ID: $USER_ID" \
  -d '{"parameters": {}, "input_data": {}}')

WORKFLOW_ID=$(echo "$EXEC_RESPONSE" | jq -r '.workflow_id')
EXECUTION_ID=$(echo "$EXEC_RESPONSE" | jq -r '.execution_id')

echo "Workflow ID: $WORKFLOW_ID"
echo "Execution ID: $EXECUTION_ID"
echo ""

# Wait for execution to reach approval node
sleep 2

# 3. Check if workflow appears in My Workflows
echo "3. Checking if workflow appears in My Workflows..."
WORKFLOW_CHECK=$(curl -s "$BASE_URL/api/workflows" | jq ".workflows[] | select(.id == \"$WORKFLOW_ID\")")
HAS_BADGE=$(echo "$WORKFLOW_CHECK" | jq -r '.source_template.template_is_public')
echo "Workflow found: $(if [ -n "$WORKFLOW_CHECK" ]; then echo "YES"; else echo "NO"; fi)"
echo "Has 'From Gallery' badge data: $HAS_BADGE"
echo ""

# 4. Check if approval appears in Inbox
echo "4. Checking if approval appears in Inbox..."
APPROVAL_CHECK=$(curl -s "$BASE_URL/api/workflow-approvals/inbox" -H "X-User-ID: $USER_ID" | jq ".[] | select(.execution_id == \"$EXECUTION_ID\")")
echo "Approval found: $(if [ -n "$APPROVAL_CHECK" ]; then echo "YES"; else echo "NO"; fi)"
if [ -n "$APPROVAL_CHECK" ]; then
  echo "Approval details:"
  echo "$APPROVAL_CHECK" | jq '{id, status, approval_prompt}'
fi
echo ""

echo "✅ Test complete!"
echo ""
echo "Summary:"
echo "  - Workflow created from public template: $WORKFLOW_ID"
echo "  - Execution ID: $EXECUTION_ID"
echo "  - Should show 'From Gallery' badge in My Workflows"
echo "  - Should show approval in Inbox"
