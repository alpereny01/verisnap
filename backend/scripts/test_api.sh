#!/bin/bash

# VeriSnap API Test Script
# Bu script API endpoint'lerini test eder

BASE_URL="http://localhost:8000"
API_BASE="$BASE_URL/api/v1"

echo "🧪 VeriSnap API Test Script"
echo "=========================="

# Health check
echo "📊 Testing health endpoint..."
curl -s "$BASE_URL/api/v1/system/health" | python -m json.tool 2>/dev/null || echo "Health endpoint test failed"

echo ""

# Root endpoint
echo "🏠 Testing root endpoint..."
curl -s "$BASE_URL/" | python -m json.tool 2>/dev/null || echo "Root endpoint test failed"

echo ""

# Login test
echo "🔐 Testing authentication..."
TOKEN=$(curl -s -X POST "$API_BASE/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=admin123" | python -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('access_token', ''))
except:
    pass" 2>/dev/null)

if [ -n "$TOKEN" ]; then
    echo "✅ Authentication successful"
    
    # Test authenticated endpoint
    echo "👤 Testing user info..."
    curl -s -X GET "$API_BASE/auth/me" \
      -H "Authorization: Bearer $TOKEN" | python -m json.tool 2>/dev/null || echo "User info test failed"
    
    echo ""
    
    # Test scraping endpoint
    echo "🔍 Testing scraping endpoint..."
    curl -s -X POST "$API_BASE/scraping/start" \
      -H "Authorization: Bearer $TOKEN" \
      -H "Content-Type: application/json" \
      -d '{
        "target_site": "jameda.de",
        "specialty": "hausarzt",
        "city": "berlin",
        "max_pages": 2
      }' | python -m json.tool 2>/dev/null || echo "Scraping test failed"
    
else
    echo "❌ Authentication failed"
fi

echo ""
echo "🎯 Test completed!"
echo "Visit $BASE_URL/docs for interactive API documentation"