#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# Acty Project - Deployment Quick Start
# ═══════════════════════════════════════════════════════════════════════════════
#
# This script automates the deployment verification and startup process.
# Usage: bash deploy.sh [dev|prod]
#
# ═══════════════════════════════════════════════════════════════════════════════

set -e  # Exit on error

ENVIRONMENT="${1:-dev}"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}═══════════════════════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}Acty Project Deployment - ${ENVIRONMENT} Environment${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════════════════════${NC}"
echo

# ── Step 1: Verify Prerequisites ──────────────────────────────────────────────
echo -e "${YELLOW}Step 1: Verifying prerequisites...${NC}"

if ! command -v docker &> /dev/null; then
    echo -e "${RED}✗ Docker not found. Install from https://docs.docker.com/get-docker/${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Docker installed ($(docker --version | cut -d' ' -f3))${NC}"

if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}✗ Docker Compose not found.${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Docker Compose installed${NC}"

if [ ! -f "$PROJECT_ROOT/.env" ]; then
    echo -e "${YELLOW}⚠ .env file not found. Creating from .env.example...${NC}"
    cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/.env"
    echo -e "${YELLOW}  → Edit .env with your configuration before deploying${NC}"
fi

if [ ! -f "$PROJECT_ROOT/docker-compose.yml" ]; then
    echo -e "${RED}✗ docker-compose.yml not found${NC}"
    exit 1
fi
echo -e "${GREEN}✓ docker-compose.yml found${NC}"

echo -e "${GREEN}✓ All prerequisites verified${NC}"
echo

# ── Step 2: Build Docker Images ───────────────────────────────────────────────
echo -e "${YELLOW}Step 2: Building Docker images...${NC}"
cd "$PROJECT_ROOT"
docker compose build --quiet 2>/dev/null || {
    echo -e "${RED}✗ Docker build failed${NC}"
    exit 1
}
echo -e "${GREEN}✓ Docker images built successfully${NC}"
echo

# ── Step 3: Start Services ────────────────────────────────────────────────────
echo -e "${YELLOW}Step 3: Starting services...${NC}"
docker compose up -d 2>/dev/null || {
    echo -e "${RED}✗ Failed to start services${NC}"
    exit 1
}
echo -e "${GREEN}✓ Services started${NC}"
echo

# ── Step 4: Wait for Services to Be Healthy ────────────────────────────────────
echo -e "${YELLOW}Step 4: Waiting for services to be healthy (max 30s)...${NC}"
TIMEOUT=30
START_TIME=$(date +%s)

while [ $(($(date +%s) - START_TIME)) -lt $TIMEOUT ]; do
    HEALTHY=$(docker compose ps | grep "healthy" | wc -l)
    EXPECTED=3  # api, postgres, others
    
    if [ $HEALTHY -ge $EXPECTED ]; then
        echo -e "${GREEN}✓ All services healthy${NC}"
        break
    fi
    
    echo -n "."
    sleep 2
done

if [ $(($(date +%s) - START_TIME)) -ge $TIMEOUT ]; then
    echo -e "${YELLOW}⚠ Timeout waiting for services. Checking status...${NC}"
fi
echo

# ── Step 5: Verify API Health ──────────────────────────────────────────────────
echo -e "${YELLOW}Step 5: Verifying API health...${NC}"
sleep 2  # Extra wait for API startup

if curl -f http://localhost:8765/health &>/dev/null; then
    echo -e "${GREEN}✓ API is responding${NC}"
else
    echo -e "${YELLOW}⚠ API not responding yet. Continuing...${NC}"
fi
echo

# ── Step 6: Display Service Endpoints ──────────────────────────────────────────
echo -e "${GREEN}═══════════════════════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✓ Deployment Complete!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════════════════════════${NC}"
echo
echo -e "${BLUE}Service Endpoints:${NC}"
echo "  API               → http://localhost:8765"
echo "  API Docs          → http://localhost:8765/docs"
echo "  Grafana Dashboard → http://localhost:3000 (admin/admin)"
echo "  Database          → postgres://localhost:5432"
echo
echo -e "${BLUE}Useful Commands:${NC}"
echo "  View logs         → docker compose logs -f api"
echo "  Check status      → docker compose ps"
echo "  Stop services     → docker compose down"
echo "  Restart API       → docker compose restart api"
echo
echo -e "${BLUE}Deployment Docs:${NC}"
echo "  Full checklist    → cat DEPLOYMENT_CHECKLIST.md"
echo "  Configuration    → cat .env.example"
echo "  API Reference     → http://localhost:8765/docs"
echo
echo -e "${YELLOW}Next Steps:${NC}"
echo "  1. Review .env configuration"
echo "  2. Load OBD CSV data via API: curl -F 'file=@data.csv' http://localhost:8765/upload"
echo "  3. Monitor via Grafana dashboard"
echo "  4. Review deployment checklist before production:"
echo "     → https://github.com/acty-labs/acty-project/blob/main/DEPLOYMENT_CHECKLIST.md"
echo
