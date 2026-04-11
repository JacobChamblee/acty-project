#!/usr/bin/env bash
# setup_2u_postgres.sh — PostgreSQL 16 setup on the 2U DIY server (192.168.68.117)
#
# Run this script ON the 2U server as a user with sudo access.
# It installs Docker, starts PostgreSQL 16 in a container, applies all
# Acty schema migrations, and prints the DATABASE_URL to paste into .env.
#
# Usage:
#   scp scripts/setup_2u_postgres.sh user@192.168.68.117:~/
#   ssh user@192.168.68.117 'bash ~/setup_2u_postgres.sh'
#
# After this script completes, copy the DATABASE_URL into:
#   - /home/<user>/acty-project-new/.env      (4U server)
#   - /home/<user>/acty-project-new/mcp/.env.mcp

set -euo pipefail

# ── Config ────────────────────────────────────────────────────────────────────
DB_NAME="acty-postgres"
DB_USER="acty"
# Generate a strong password if not already set
DB_PASSWORD="${ACTY_DB_PASSWORD:-$(openssl rand -base64 24 | tr -d '/+=' | head -c 32)}"
CONTAINER_NAME="acty-postgres"
PG_VERSION="16"
DATA_DIR="/opt/acty/pgdata"
SCRIPTS_DIR="$(dirname "$0")"

echo "=== Acty PostgreSQL Setup (2U server) ==="
echo "DB: $DB_NAME  User: $DB_USER"
echo ""

# ── 1. Install Docker if missing ──────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
    echo "[1/6] Installing Docker..."
    curl -fsSL https://get.docker.com | sudo bash
    sudo usermod -aG docker "$USER"
    echo "      Docker installed. You may need to log out and back in."
    echo "      Re-run this script after logging back in to continue."
    exit 0
else
    echo "[1/6] Docker already installed: $(docker --version)"
fi

# ── 2. Create data directory ──────────────────────────────────────────────────
echo "[2/6] Creating data directory: $DATA_DIR"
sudo mkdir -p "$DATA_DIR"
sudo chown "$USER":"$USER" "$DATA_DIR"

# ── 3. Stop existing container if running ─────────────────────────────────────
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "[3/6] Stopping existing $CONTAINER_NAME container..."
    docker stop "$CONTAINER_NAME" 2>/dev/null || true
    docker rm   "$CONTAINER_NAME" 2>/dev/null || true
else
    echo "[3/6] No existing $CONTAINER_NAME container found — clean start"
fi

# ── 4. Start PostgreSQL 16 ────────────────────────────────────────────────────
echo "[4/6] Starting PostgreSQL $PG_VERSION container..."
docker run -d \
    --name "$CONTAINER_NAME" \
    --restart unless-stopped \
    -e POSTGRES_USER="$DB_USER" \
    -e POSTGRES_PASSWORD="$DB_PASSWORD" \
    -e POSTGRES_DB="$DB_NAME" \
    -p 5432:5432 \
    -v "$DATA_DIR":/var/lib/postgresql/data \
    "postgres:${PG_VERSION}-alpine"

echo "      Waiting for PostgreSQL to become ready..."
for i in $(seq 1 30); do
    if docker exec "$CONTAINER_NAME" pg_isready -U "$DB_USER" -d "$DB_NAME" &>/dev/null; then
        echo "      PostgreSQL ready after ${i}s"
        break
    fi
    sleep 1
done

# Verify it's actually up
docker exec "$CONTAINER_NAME" pg_isready -U "$DB_USER" -d "$DB_NAME" || {
    echo "ERROR: PostgreSQL did not become ready. Check: docker logs $CONTAINER_NAME"
    exit 1
}

# ── 5. Apply schema migrations in order ───────────────────────────────────────
echo "[5/6] Applying schema migrations..."

apply_sql() {
    local file="$1"
    local label="$2"
    if [[ -f "$file" ]]; then
        echo "      Applying: $label"
        docker exec -i "$CONTAINER_NAME" \
            psql -U "$DB_USER" -d "$DB_NAME" < "$file"
    else
        echo "      SKIP (not found): $file"
    fi
}

# Resolve script location — works whether called with absolute or relative path
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

apply_sql "$SCRIPT_DIR/init_db.sql"                    "init_db.sql (base schema)"
apply_sql "$SCRIPT_DIR/migrate_add_user_llm_configs.sql" "migrate_add_user_llm_configs.sql (users + BYOK)"
apply_sql "$SCRIPT_DIR/migrate_beta_schema.sql"        "migrate_beta_schema.sql (beta fixes: owner_id, obd_adapters, jobs)"

# ── 6. Verify tables ──────────────────────────────────────────────────────────
echo "[6/6] Verifying tables..."
TABLES=$(docker exec "$CONTAINER_NAME" \
    psql -U "$DB_USER" -d "$DB_NAME" -tAc \
    "SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name;")

echo "      Tables found:"
echo "$TABLES" | sed 's/^/        /'

EXPECTED=(
    alerts anomaly_results app_user_accounts diagnostic_reports
    jobs maintenance_predictions obd_adapters ollama_analyses
    session_rows sessions user_llm_configs users vehicles
)
MISSING=()
for t in "${EXPECTED[@]}"; do
    echo "$TABLES" | grep -q "^${t}$" || MISSING+=("$t")
done

if [[ ${#MISSING[@]} -eq 0 ]]; then
    echo "      All expected tables present ✓"
else
    echo "      WARNING: missing tables: ${MISSING[*]}"
fi

# ── Print connection info ─────────────────────────────────────────────────────
LOCAL_IP=$(hostname -I | awk '{print $1}')
DATABASE_URL="postgresql://${DB_USER}:${DB_PASSWORD}@${LOCAL_IP}:5432/${DB_NAME}"

echo ""
echo "=========================================================="
echo " PostgreSQL is UP on ${LOCAL_IP}:5432"
echo " Database : $DB_NAME"
echo " User     : $DB_USER"
echo " Password : $DB_PASSWORD"
echo ""
echo " DATABASE_URL (paste into 4U .env and mcp/.env.mcp):"
echo " $DATABASE_URL"
echo "=========================================================="
echo ""
echo "Next steps on the 4U server (192.168.68.138):"
echo "  1. Edit ~/acty-project-new/.env:"
echo "       DATABASE_URL=$DATABASE_URL"
echo "  2. Edit ~/acty-project-new/mcp/.env.mcp:"
echo "       ACTY_DB_DSN=$DATABASE_URL"
echo "  3. Restart the API:"
echo "       cd ~/acty-project-new && docker compose -f docker-compose.prod.yml up -d --force-recreate api"
echo "  4. Restart MCP:"
echo "       sudo systemctl restart acty-mcp"
echo ""
echo "Firewall: if psql from 4U fails, open port 5432 on this machine:"
echo "  sudo ufw allow from 192.168.68.138 to any port 5432"
echo "  sudo ufw allow from 192.168.68.121 to any port 5432   # CM3588"
echo ""

# Save credentials to a local file for reference
cat > ~/acty_db_credentials.txt << EOF
# Acty PostgreSQL credentials — $(date)
DATABASE_URL=$DATABASE_URL
DB_PASSWORD=$DB_PASSWORD
EOF
chmod 600 ~/acty_db_credentials.txt
echo "Credentials saved to ~/acty_db_credentials.txt (chmod 600)"
