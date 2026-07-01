#!/bin/bash
# Complete test for Make.com integration with email

# Configuration
WEBHOOK_URL="https://schaffnermac-6-1.risk-tailor.ts.net/run"
SECRET="change-me"
PDF_FILE="bs.pdf"
GIG_NAME="Make.com Test - $(date '+%Y-%m-%d %H:%M')"

echo "🧪 Complete Make.com Integration Test"
echo "=================================="
echo "📄 PDF: $PDF_FILE"
echo "🎵 Gig: $GIG_NAME"
echo "🔗 URL: $WEBHOOK_URL"
echo "📧 Email: brian@schaffner.net"
echo ""

# Check if PDF exists
if [ ! -f "$PDF_FILE" ]; then
    echo "❌ Error: $PDF_FILE not found"
    exit 1
fi

echo "📤 Sending request to Make.com webhook..."

# Send POST request with PDF
response=$(curl -s -w "\n%{http_code}" \
    -X POST \
    -H "X-Secret: $SECRET" \
    -F "name=$GIG_NAME" \
    -F "file=@$PDF_FILE" \
    "$WEBHOOK_URL")

# Extract HTTP status code (last line)
http_code=$(echo "$response" | tail -n1)
# Extract response body (all but last line)
response_body=$(echo "$response" | sed '$d')

echo "📊 Response:"
echo "Status Code: $http_code"
echo "Response Body: $response_body"
echo ""

if [ "$http_code" = "200" ]; then
    echo "✅ Success! Make.com webhook received the request"
    
    # Parse the response to get artifact info
    artifact_path=$(echo "$response_body" | grep -o '"artifact":"[^"]*"' | cut -d'"' -f4)
    emailed=$(echo "$response_body" | grep -o '"emailed":[^,}]*' | cut -d':' -f2)
    
    echo "📁 Generated Artifact: $artifact_path"
    echo "📧 Email Sent: $emailed"
    
    if [ -f "$artifact_path" ]; then
        echo "✅ Artifact file exists: $(ls -lh "$artifact_path" | awk '{print $5}')"
    else
        echo "⚠️  Artifact file not found at expected location"
    fi
    
    echo ""
    echo "🎉 Test completed successfully!"
    echo "📧 Check your email for the generated .sbp file"
    echo "📁 Check the pack/ directory for the generated files"
    
else
    echo "❌ Error: HTTP $http_code"
    echo "Response: $response_body"
    exit 1
fi

