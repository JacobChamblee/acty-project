#!/bin/bash
# Production Monitoring Script for Acty Labs
# Monitors CM3588 server and backend services
# Run this script to check production deployment status

set -e

# Configuration
CM3588_HOST="pi@192.168.68.121"
BACKEND_HOST="192.168.68.138"
WEBSITE_URL="https://acty-labs.com"
API_URL="https://api.acty-labs.com"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🔍 Acty Labs Production Monitoring${NC}"
echo "=================================="

# Function to check HTTP status
check_http() {
    local url=$1
    local expected_code=${2:-200}
    local name=$3

    echo -n "Checking $name ($url)... "
    local status_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$url" 2>/dev/null || echo "000")

    if [ "$status_code" = "$expected_code" ]; then
        echo -e "${GREEN}✅ $status_code${NC}"
        return 0
    else
        echo -e "${RED}❌ $status_code (expected $expected_code)${NC}"
        return 1
    fi
}

# Function to check SSL certificate
check_ssl() {
    local domain=$1
    local name=$2

    echo -n "Checking SSL for $name... "
    if echo | openssl s_client -servername "$domain" -connect "$domain":443 2>/dev/null | openssl x509 -noout -checkend 86400 >/dev/null 2>&1; then
        echo -e "${GREEN}✅ Valid${NC}"
        return 0
    else
        echo -e "${RED}❌ Invalid or expiring${NC}"
        return 1
    fi
}

# Check website
echo -e "${YELLOW}🌐 Website Status${NC}"
check_http "$WEBSITE_URL" 200 "Main Website"
check_ssl "acty-labs.com" "Main Website"

# Check API
echo -e "\n${YELLOW}🔌 API Status${NC}"
check_http "$API_URL/health" 200 "API Health"
check_ssl "api.acty-labs.com" "API SSL"

# Check backend services (direct access)
echo -e "\n${YELLOW}⚙️  Backend Services${NC}"
echo -n "Checking backend API (direct)... "
if curl -s --max-time 5 "http://$BACKEND_HOST:8765/health" >/dev/null 2>&1; then
    echo -e "${GREEN}✅ OK${NC}"
else
    echo -e "${RED}❌ Failed${NC}"
fi

# Check CM3588 Caddy service
echo -e "\n${YELLOW}🖥️  CM3588 Server Status${NC}"
echo -n "Checking Caddy service... "
if ssh -o ConnectTimeout=5 "$CM3588_HOST" "sudo systemctl is-active caddy" 2>/dev/null | grep -q "active"; then
    echo -e "${GREEN}✅ Active${NC}"
else
    echo -e "${RED}❌ Inactive${NC}"
fi

# Check Docker services on backend
echo -e "\n${YELLOW}🐳 Docker Services${NC}"
echo -n "Checking Docker containers... "
if ssh -o ConnectTimeout=5 "pi@$BACKEND_HOST" "docker ps --format 'table {{.Names}}\t{{.Status}}'" 2>/dev/null; then
    echo -e "${GREEN}✅ Running${NC}"
    ssh -o ConnectTimeout=5 "pi@$BACKEND_HOST" "docker ps --format 'table {{.Names}}\t{{.Status}}'" 2>/dev/null
else
    echo -e "${RED}❌ Failed to check${NC}"
fi

# Show recent logs
echo -e "\n${YELLOW}📋 Recent Logs${NC}"
echo "Caddy access logs (last 5 entries):"
ssh "$CM3588_HOST" "sudo tail -5 /var/log/caddy/acty-labs.log 2>/dev/null || echo 'No logs found'" 2>/dev/null

echo -e "\nAPI logs (last 5 entries):"
ssh "$CM3588_HOST" "sudo tail -5 /var/log/caddy/api.acty-labs.log 2>/dev/null || echo 'No logs found'" 2>/dev/null

# Performance check
echo -e "\n${YELLOW}⚡ Performance${NC}"
echo -n "Website response time... "
response_time=$(curl -s -o /dev/null -w "%{time_total}" "$WEBSITE_URL" 2>/dev/null || echo "0")
if (( $(echo "$response_time < 2.0" | bc -l 2>/dev/null) )); then
    echo -e "${GREEN}✅ ${response_time}s${NC}"
else
    echo -e "${YELLOW}⚠️  ${response_time}s (slow)${NC}"
fi

echo -e "\n${BLUE}Monitoring complete. Run this script again to check status.${NC}"