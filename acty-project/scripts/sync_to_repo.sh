#!/usr/bin/env bash
# sync_to_repo.sh
# ---------------
# Syncs the consolidated Acty project structure into your existing
# JacobChamblee/acty-project GitHub repo.
#
# Usage:
#   cd ~/path/to/acty-project   # your existing git clone
#   bash sync_to_repo.sh /path/to/extracted/acty-project
#
# What it does:
#   - Copies all files from the consolidated source tree
#   - Does NOT delete any files already in your repo that aren't in the source
#   - Prints a summary of what changed so you can review before committing
#
# After running, do:
#   git diff --stat
#   git add -A
#   git commit -m "chore: consolidate repo structure, remove redundant copies"
#   git push

set -euo pipefail

SOURCE="${1:-$(dirname "$0")}"
DEST="${2:-$(pwd)}"

if [ ! -d "$SOURCE/backend" ]; then
  echo "ERROR: Source doesn't look right — backend/ not found in $SOURCE"
  echo "Usage: bash sync_to_repo.sh /path/to/consolidated/acty-project"
  exit 1
fi

if [ ! -d "$DEST/.git" ]; then
  echo "ERROR: $DEST is not a git repository"
  exit 1
fi

echo "=== Acty repo sync ==="
echo "  Source: $SOURCE"
echo "  Dest:   $DEST"
echo ""

# Directories to sync
DIRS=(
  "backend"
  "frontend"
  "hardware"
  "scripts"
  "docs"
)

# Root files to copy
ROOT_FILES=(
  ".gitignore"
  ".env.example"
  "README.md"
  "requirements.txt"
  "docker-compose.yml"
)

# Remove old redundant directories if they exist
OLD_DIRS=(
  "RAGpipeline"
  "acty bridge"
  "acty-fsm-rag"
  "acty"
  "android mobile app"
)

echo "[1/4] Removing redundant old directories..."
for d in "${OLD_DIRS[@]}"; do
  if [ -d "$DEST/$d" ]; then
    echo "  rm -rf '$DEST/$d'"
    rm -rf "$DEST/$d"
  fi
done

# Remove old root-level Python scripts that are now organized
OLD_FILES=(
  "acty_obd.py"
  "acty_obd_capture.py"
  "battery_health.py"
  "maintenance_tracker.py"
  "oil_change_detector.py"
  "oil_interval_advisor.py"
  "oil_level_estimator.py"
)

echo ""
echo "[2/4] Removing old root-level files..."
for f in "${OLD_FILES[@]}"; do
  if [ -f "$DEST/$f" ]; then
    echo "  rm '$DEST/$f'"
    rm -f "$DEST/$f"
  fi
done

echo ""
echo "[3/4] Copying root files..."
for f in "${ROOT_FILES[@]}"; do
  if [ -f "$SOURCE/$f" ]; then
    cp "$SOURCE/$f" "$DEST/$f"
    echo "  $f ✓"
  fi
done

echo ""
echo "[4/4] Syncing directories..."
for d in "${DIRS[@]}"; do
  if [ -d "$SOURCE/$d" ]; then
    mkdir -p "$DEST/$d"
    rsync -av --delete "$SOURCE/$d/" "$DEST/$d/" 2>/dev/null || \
      cp -r "$SOURCE/$d/." "$DEST/$d/"
    echo "  $d/ ✓"
  fi
done

echo ""
echo "=== Sync complete ==="
echo ""
echo "Review changes:"
echo "  cd $DEST && git diff --stat"
echo ""
echo "Commit when ready:"
echo "  git add -A"
echo "  git commit -m 'chore: consolidate repo — remove duplicate RAG copies, organize by layer'"
echo "  git push origin main"
