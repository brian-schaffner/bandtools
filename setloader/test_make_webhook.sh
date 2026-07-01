#!/bin/bash
# Test script to send PDF to Make.com webhook

# Configuration
WEBHOOK_URL="https://schaffnermac-6-1.risk-tailor.ts.net/run"
SECRET="change-me"
PDF_FILE="bs.pdf"
GIG_NAME="Test Gig - SetLoader Integration"

echo "🧪 Testing Make.com webhook integration..."
echo "📄 PDF: $PDF_FILE"
echo "🎵 Gig: $GIG_NAME"
echo "🔗 URL: $WEBHOOK_URL"
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

if [ "$http_code" = "200" ]; then
    echo "✅ Success! Make.com webhook received the request"
    echo "📧 Check your email for the generated .sbp file"
else
    echo "❌ Error: HTTP $http_code"
    echo "Response: $response_body"
    exit 1
fi
