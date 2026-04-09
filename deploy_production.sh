#!/bin/bash
# Production Deployment Script for Acty Labs
# Deploys frontend build to CM3588 server (192.168.68.121)
# Run this script from the acty-project root directory

set -e  # Exit on any error

echo "🚀 Starting Acty Labs Production Deployment"

# Configuration
CM3588_HOST="pi@192.168.68.121"
REMOTE_PATH="/home/pi/acty-site"
BUILD_DIR="./frontend/build"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if build directory exists
if [ ! -d "$BUILD_DIR" ]; then
    echo -e "${RED}❌ Error: Build directory $BUILD_DIR not found!${NC}"
    echo "Please run 'npm run build' in the frontend directory first."
    exit 1
fi

echo -e "${YELLOW}📦 Checking build contents...${NC}"
ls -la "$BUILD_DIR"

# Create remote directory structure
echo -e "${YELLOW}📁 Creating remote directories...${NC}"
ssh "$CM3588_HOST" "mkdir -p $REMOTE_PATH/build"

# Copy build files to CM3588
echo -e "${YELLOW}📤 Copying build files to CM3588 server...${NC}"
rsync -avz --delete "$BUILD_DIR/" "$CM3588_HOST:$REMOTE_PATH/build/"

# Copy updated Caddyfile
echo -e "${YELLOW}📋 Copying updated Caddyfile...${NC}"
scp "./Caddyfile" "$CM3588_HOST:/etc/caddy/Caddyfile"

# Copy SSL certificates (if they exist locally)
if [ -f "./ssl/acty-labs.com.pem" ] && [ -f "./ssl/acty-labs.com.key" ]; then
    echo -e "${YELLOW}🔐 Copying SSL certificates...${NC}"
    ssh "$CM3588_HOST" "sudo mkdir -p /etc/ssl/certs /etc/ssl/private"
    scp "./ssl/acty-labs.com.pem" "$CM3588_HOST:/tmp/cert.pem"
    scp "./ssl/acty-labs.com.key" "$CM3588_HOST:/tmp/cert.key"
    ssh "$CM3588_HOST" "sudo mv /tmp/cert.pem /etc/ssl/certs/acty-labs.com.pem"
    ssh "$CM3588_HOST" "sudo mv /tmp/cert.key /etc/ssl/private/acty-labs.com.key"
    ssh "$CM3588_HOST" "sudo chmod 644 /etc/ssl/certs/acty-labs.com.pem"
    ssh "$CM3588_HOST" "sudo chmod 600 /etc/ssl/private/acty-labs.com.key"
else
    echo -e "${YELLOW}⚠️  SSL certificates not found locally. Make sure they're configured on CM3588.${NC}"
fi

# Reload Caddy configuration
echo -e "${YELLOW}🔄 Reloading Caddy configuration...${NC}"
ssh "$CM3588_HOST" "sudo systemctl reload caddy"

# Verify deployment
echo -e "${YELLOW}✅ Verifying deployment...${NC}"
echo "Testing website accessibility..."
if curl -s -o /dev/null -w "%{http_code}" https://acty-labs.com | grep -q "200"; then
    echo -e "${GREEN}✅ Website is accessible at https://acty-labs.com${NC}"
else
    echo -e "${RED}❌ Website not accessible. Check Caddy logs.${NC}"
fi

# Check Caddy status
echo "Checking Caddy service status..."
ssh "$CM3588_HOST" "sudo systemctl status caddy --no-pager -l"

echo -e "${GREEN}🎉 Deployment completed!${NC}"
echo ""
echo "Next steps:"
echo "1. Test the website: https://acty-labs.com"
echo "2. Test API endpoints: https://api.acty-labs.com/health"
echo "3. Check Caddy logs: ssh $CM3588_HOST 'sudo journalctl -u caddy -f'"
echo "4. Monitor performance and logs"