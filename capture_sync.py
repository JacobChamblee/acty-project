#!/usr/bin/env python3
"""
capture_sync.py
---------------
Syncs new OBD capture CSVs from the local data_capture folder to the
TrueNAS SMB share, only when connected to the home LAN.

Local:  ~/acty-project/data_capture/
Remote: //truenas.local/share1/acty-project/data_capture/

Logic:
  1. Check home LAN connectivity by pinging truenas.local
  2. Mount the SMB share (if not already mounted)
  3. Compare local CSVs against remote — copy only files not already there
  4. Record synced filenames in a local manifest (.sync_manifest) to
     avoid re-scanning the remote on every run
  5. Unmount after sync (optional — see KEEP_MOUNTED)

Usage:
    python3 capture_sync.py              # sync all new files
    python3 capture_sync.py --dry-run    # show what would be synced
    python3 capture_sync.py --status     # show sync status only
    python3 capture_sync.py --force      # ignore manifest, re-check remote

Requirements:
    sudo apt install cifs-utils
    Add to /etc/sudoers (visudo):
        jacob ALL=(ALL) NOPASSWD: /usr/bin/mount, /usr/bin/umount
"""

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# ─── CONFIG ──────────────────────────────────────────────────────────────────

TRUENAS_HOST    = "truenas.local"
SMB_SHARE       = f"//{TRUENAS_HOST}/share1"
SMB_USER        = "jacob"

# Password can be set via env var ACTY_SMB_PASSWORD or prompted at runtime
SMB_PASSWORD    = os.environ.get("ACTY_SMB_PASSWORD", "")

LOCAL_DATA_DIR  = Path.home() / "acty-project" / "data_capture"
MOUNT_POINT     = Path("/mnt/truenas-share1")
REMOTE_DATA_DIR = MOUNT_POINT / "acty-project" / "data_capture"
MANIFEST_FILE   = LOCAL_DATA_DIR / ".sync_manifest"

# Set True to leave the share mounted after sync (faster repeated runs)
KEEP_MOUNTED    = False

# ─── HELPERS ─────────────────────────────────────────────────────────────────

def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def is_home_lan() -> bool:
    """Ping truenas.local — returns True if reachable."""
    try:
        result = subprocess.run(
            ["ping", "-c", "1", "-W", "2", TRUENAS_HOST],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def is_mounted() -> bool:
    """Check if the SMB share is already mounted."""
    result = subprocess.run(["mountpoint", "-q", str(MOUNT_POINT)])
    return result.returncode == 0


def mount_share(password: str) -> bool:
    """Mount the SMB share. Returns True on success."""
    MOUNT_POINT.mkdir(parents=True, exist_ok=True)
    cmd = [
        "sudo", "mount", "-t", "cifs", SMB_SHARE, str(MOUNT_POINT),
        "-o", f"username={SMB_USER},password={password},"
              f"uid={os.getuid()},gid={os.getgid()},"
              f"iocharset=utf8,file_mode=0664,dir_mode=0775",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        log(f"[ERROR] Mount failed: {result.stderr.strip()}")
        return False
    return True


def unmount_share() -> bool:
    """Unmount the SMB share."""
    result = subprocess.run(
        ["sudo", "umount", str(MOUNT_POINT)],
        capture_output=True, text=True,
    )
    return result.returncode == 0


def load_manifest() -> set:
    """Load the set of already-synced filenames from the manifest."""
    if not MANIFEST_FILE.exists():
        return set()
    try:
        data = json.loads(MANIFEST_FILE.read_text())
        return set(data.get("synced", []))
    except (json.JSONDecodeError, KeyError):
        return set()


def save_manifest(synced: set):
    """Persist the set of synced filenames."""
    MANIFEST_FILE.write_text(json.dumps({"synced": sorted(synced)}, indent=2))


def get_remote_files() -> set:
    """Return set of filenames already present on the remote."""
    if not REMOTE_DATA_DIR.exists():
        REMOTE_DATA_DIR.mkdir(parents=True, exist_ok=True)
        return set()
    return {f.name for f in REMOTE_DATA_DIR.iterdir() if f.is_file()}


def get_local_csvs() -> list[Path]:
    """Return sorted list of CSV files in the local data_capture dir."""
    if not LOCAL_DATA_DIR.exists():
        return []
    return sorted(LOCAL_DATA_DIR.glob("acty_obd_*.csv"))


# ─── MAIN ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Sync Acty OBD CSVs to TrueNAS")
    parser.add_argument("--dry-run",  action="store_true", help="Show what would sync, don't copy")
    parser.add_argument("--status",   action="store_true", help="Show sync status and exit")
    parser.add_argument("--force",    action="store_true", help="Ignore manifest, re-check remote")
    args = parser.parse_args()

    # ── Preflight ─────────────────────────────────────────────────────────────
    local_csvs = get_local_csvs()
    log(f"Local data_capture: {len(local_csvs)} CSV file(s) found")

    if args.status:
        manifest = load_manifest()
        unsynced = [f for f in local_csvs if f.name not in manifest]
        log(f"Manifest: {len(manifest)} file(s) previously synced")
        log(f"Pending sync: {len(unsynced)} file(s)")
        for f in unsynced:
            print(f"  → {f.name}")
        sys.exit(0)

    if not local_csvs:
        log("No CSV files to sync. Exiting.")
        sys.exit(0)

    # ── LAN check ────────────────────────────────────────────────────────────
    log(f"Checking home LAN ({TRUENAS_HOST})...")
    if not is_home_lan():
        log("Not on home LAN — skipping sync.")
        sys.exit(0)
    log("Home LAN detected ✓")

    # ── Determine new files ───────────────────────────────────────────────────
    manifest = load_manifest() if not args.force else set()

    # Files not in manifest are candidates
    candidates = [f for f in local_csvs if f.name not in manifest]

    if not candidates:
        log("All local files already in sync manifest — nothing to do.")
        log("Run with --force to re-verify against remote.")
        sys.exit(0)

    log(f"{len(candidates)} candidate file(s) not yet in manifest")

    # ── Mount ─────────────────────────────────────────────────────────────────
    mounted_here = False
    if not is_mounted():
        password = SMB_PASSWORD
        if not password:
            import getpass
            password = getpass.getpass(f"SMB password for {SMB_USER}@{TRUENAS_HOST}: ")

        log(f"Mounting {SMB_SHARE} → {MOUNT_POINT}...")
        if not mount_share(password):
            log("Cannot mount share — aborting.")
            sys.exit(1)
        mounted_here = True
        log("Share mounted ✓")
    else:
        log(f"Share already mounted at {MOUNT_POINT}")

    try:
        # ── Cross-check against remote ────────────────────────────────────────
        remote_files = get_remote_files()
        log(f"Remote has {len(remote_files)} file(s) in data_capture/")

        to_copy = [f for f in candidates if f.name not in remote_files]
        already_remote = [f for f in candidates if f.name in remote_files]

        # Files already on remote — add to manifest without copying
        if already_remote:
            log(f"{len(already_remote)} file(s) already on remote (updating manifest):")
            for f in already_remote:
                log(f"  = {f.name}")
            if not args.dry_run:
                manifest.update(f.name for f in already_remote)

        if not to_copy:
            log("Nothing new to copy.")
        else:
            log(f"Copying {len(to_copy)} new file(s):")
            copied = []
            failed = []
            for src in to_copy:
                dst = REMOTE_DATA_DIR / src.name
                if args.dry_run:
                    size_kb = src.stat().st_size / 1024
                    log(f"  [DRY RUN] would copy: {src.name}  ({size_kb:.1f} KB)")
                    continue
                try:
                    shutil.copy2(src, dst)
                    size_kb = src.stat().st_size / 1024
                    log(f"  ✓ {src.name}  ({size_kb:.1f} KB)")
                    copied.append(src.name)
                except Exception as e:
                    log(f"  ✗ {src.name}  ERROR: {e}")
                    failed.append(src.name)

            if not args.dry_run:
                manifest.update(copied)
                if failed:
                    log(f"[WARN] {len(failed)} file(s) failed to copy — will retry next run")

        # ── Save manifest ─────────────────────────────────────────────────────
        if not args.dry_run:
            save_manifest(manifest)
            log(f"Manifest updated ({len(manifest)} total synced files)")

    finally:
        # ── Unmount ───────────────────────────────────────────────────────────
        if mounted_here and not KEEP_MOUNTED:
            if unmount_share():
                log("Share unmounted ✓")
            else:
                log("[WARN] Unmount failed — may need manual: sudo umount /mnt/truenas-share1")

    log("Sync complete.")


if __name__ == "__main__":
    main()
