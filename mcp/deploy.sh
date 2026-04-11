#!/usr/bin/env bash
# deploy.sh — Set up and start the Acty MCP server on the 4U server (192.168.68.138)
# Run as: jacob@4u-server:~/acty-project/mcp$ bash deploy.sh

set -euo pipefail

MCP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$MCP_DIR/venv"
SERVICE_NAME="acty-mcp"

echo "==> Acty MCP Server deploy"
echo "    dir: $MCP_DIR"

# ── 1. Create venv if needed ──────────────────────────────────────────────────
if [ ! -f "$VENV/bin/python" ]; then
    echo "==> Creating Python venv..."
    python3 -m venv "$VENV"
fi

# ── 2. Install / upgrade dependencies ────────────────────────────────────────
echo "==> Installing dependencies..."
"$VENV/bin/pip" install --quiet --upgrade pip
"$VENV/bin/pip" install --quiet -r "$MCP_DIR/requirements-mcp.txt"

# ── 3. Verify .env.mcp exists ────────────────────────────────────────────────
if [ ! -f "$MCP_DIR/.env.mcp" ]; then
    echo "ERROR: $MCP_DIR/.env.mcp not found."
    echo "       Copy mcp/.env.mcp from the repo and fill in real credentials."
    exit 1
fi

# ── 4. Smoke-test the server can import ──────────────────────────────────────
echo "==> Smoke-testing imports..."
"$VENV/bin/python" -c "from mcp.server.fastmcp import FastMCP; import asyncpg, httpx, dotenv; print('  imports OK')"

# ── 5. Install systemd service ────────────────────────────────────────────────
UNIT_SRC="$MCP_DIR/acty-mcp.service"
UNIT_DST="/etc/systemd/system/$SERVICE_NAME.service"

echo "==> Installing systemd unit to $UNIT_DST..."
sudo cp "$UNIT_SRC" "$UNIT_DST"
sudo sed -i "s|/home/jacob/acty-project/mcp|$MCP_DIR|g" "$UNIT_DST"
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl restart "$SERVICE_NAME"

# ── 6. Status check ──────────────────────────────────────────────────────────
sleep 2
echo "==> Service status:"
sudo systemctl status "$SERVICE_NAME" --no-pager -l | head -20

echo ""
echo "==> MCP server listening on http://$(hostname -I | awk '{print $1}'):8767/sse"
echo "    Logs: journalctl -u $SERVICE_NAME -f"
