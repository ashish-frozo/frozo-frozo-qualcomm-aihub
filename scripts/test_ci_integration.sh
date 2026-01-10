#!/bin/bash
# EdgeGate CI Integration Test Script
#
# This script simulates what a customer's GitHub Action would do:
# 1. Authenticate with HMAC signature
# 2. Trigger a run via the CI API
# 3. Poll for status
#
# Usage: ./scripts/test_ci_integration.sh <workspace_id> <api_secret> <pipeline_id> <model_artifact_id>

set -e

# Configuration
API_URL="${EDGEGATE_API_URL:-https://edgegate-api.railway.app}"
WORKSPACE_ID="${1:-$EDGEGATE_WORKSPACE_ID}"
API_SECRET="${2:-$EDGEGATE_API_SECRET}"
PIPELINE_ID="${3:-$EDGEGATE_PIPELINE_ID}"
MODEL_ARTIFACT_ID="${4:-$EDGEGATE_MODEL_ARTIFACT_ID}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=============================================="
echo "EdgeGate CI Integration Test"
echo "=============================================="
echo ""

# Validate inputs
if [ -z "$WORKSPACE_ID" ]; then
    echo -e "${RED}Error: WORKSPACE_ID is required${NC}"
    echo "Usage: $0 <workspace_id> <api_secret> <pipeline_id> <model_artifact_id>"
    echo "Or set environment variables: EDGEGATE_WORKSPACE_ID, EDGEGATE_API_SECRET, etc."
    exit 1
fi

if [ -z "$API_SECRET" ]; then
    echo -e "${RED}Error: API_SECRET is required${NC}"
    exit 1
fi

echo "API URL: $API_URL"
echo "Workspace ID: $WORKSPACE_ID"
echo ""

# Step 1: Test CI authentication
echo -e "${YELLOW}Step 1: Testing CI authentication...${NC}"

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
NONCE=$(uuidgen 2>/dev/null || cat /proc/sys/kernel/random/uuid 2>/dev/null || echo "test-nonce-$(date +%s)")

# Empty body for GET request
PAYLOAD="${TIMESTAMP}
${NONCE}
"

SIGNATURE=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "$API_SECRET" | awk '{print $2}')

STATUS_RESPONSE=$(curl -s -w "\n%{http_code}" -X GET \
    "$API_URL/v1/ci/status" \
    -H "X-EdgeGate-Workspace: $WORKSPACE_ID" \
    -H "X-EdgeGate-Timestamp: $TIMESTAMP" \
    -H "X-EdgeGate-Nonce: $NONCE" \
    -H "X-EdgeGate-Signature: $SIGNATURE")

HTTP_CODE=$(echo "$STATUS_RESPONSE" | tail -n1)
BODY=$(echo "$STATUS_RESPONSE" | head -n-1)

if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✓ Authentication successful!${NC}"
    echo "Response: $BODY"
else
    echo -e "${RED}✗ Authentication failed (HTTP $HTTP_CODE)${NC}"
    echo "Response: $BODY"
    exit 1
fi

echo ""

# Step 2: Trigger a run (if pipeline and model IDs provided)
if [ -n "$PIPELINE_ID" ] && [ -n "$MODEL_ARTIFACT_ID" ]; then
    echo -e "${YELLOW}Step 2: Triggering EdgeGate run...${NC}"
    
    TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    NONCE=$(uuidgen 2>/dev/null || cat /proc/sys/kernel/random/uuid 2>/dev/null || echo "test-nonce-$(date +%s)")
    
    BODY="{\"pipeline_id\":\"$PIPELINE_ID\",\"model_artifact_id\":\"$MODEL_ARTIFACT_ID\",\"commit_sha\":\"test-$(date +%s)\",\"branch\":\"test-branch\"}"
    
    PAYLOAD="${TIMESTAMP}
${NONCE}
${BODY}"
    
    SIGNATURE=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "$API_SECRET" | awk '{print $2}')
    
    RUN_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST \
        "$API_URL/v1/ci/github/run" \
        -H "Content-Type: application/json" \
        -H "X-EdgeGate-Workspace: $WORKSPACE_ID" \
        -H "X-EdgeGate-Timestamp: $TIMESTAMP" \
        -H "X-EdgeGate-Nonce: $NONCE" \
        -H "X-EdgeGate-Signature: $SIGNATURE" \
        -d "$BODY")
    
    HTTP_CODE=$(echo "$RUN_RESPONSE" | tail -n1)
    BODY=$(echo "$RUN_RESPONSE" | head -n-1)
    
    if [ "$HTTP_CODE" = "202" ]; then
        RUN_ID=$(echo "$BODY" | grep -o '"run_id":"[^"]*"' | cut -d'"' -f4)
        echo -e "${GREEN}✓ Run triggered successfully!${NC}"
        echo "Run ID: $RUN_ID"
        echo "Response: $BODY"
        
        echo ""
        echo "View results at: $API_URL/workspace/$WORKSPACE_ID/runs/$RUN_ID"
    else
        echo -e "${RED}✗ Failed to trigger run (HTTP $HTTP_CODE)${NC}"
        echo "Response: $BODY"
        exit 1
    fi
else
    echo -e "${YELLOW}Step 2: Skipped (no PIPELINE_ID or MODEL_ARTIFACT_ID provided)${NC}"
    echo "To trigger a test run, provide pipeline and model artifact IDs"
fi

echo ""
echo "=============================================="
echo -e "${GREEN}CI Integration Test Complete!${NC}"
echo "=============================================="
