#!/usr/bin/env python3
"""
keygen.py — CLI tool to generate API keys for Artifact.

Usage:
    python keygen.py create --label "anthropic-app" --budget 50000
    python keygen.py list
    python keygen.py revoke KEY_ID
"""

from __future__ import annotations

import argparse
import hashlib
import secrets
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parent / "data" / "keys.sqlite"


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS api_keys (
            id TEXT PRIMARY KEY,
            key_hash TEXT NOT NULL,
            label TEXT NOT NULL DEFAULT '',
            token_budget INTEGER NOT NULL DEFAULT 100000,
            tokens_used INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            last_used_at TEXT,
            active INTEGER NOT NULL DEFAULT 1
        )
    """)
    conn.commit()
    return conn


def generate_key() -> str:
    """Generate a human-readable API key: art_XXXX..."""
    token = secrets.token_hex(16)
    return f"art_{token}"


def cmd_create(args):
    conn = connect(args.db)
    key = generate_key()
    key_hash = hashlib.sha256(key.encode()).hexdigest()
    key_id = secrets.token_hex(8)
    now = datetime.now(timezone.utc).isoformat()

    conn.execute(
        """INSERT INTO api_keys (id, key_hash, label, token_budget, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        (key_id, key_hash, args.label, args.budget, now),
    )
    conn.commit()
    conn.close()

    print(f"Created API key:")
    print(f"  Key:    {key}")
    print(f"  ID:     {key_id}")
    print(f"  Label:  {args.label}")
    print(f"  Budget: {args.budget:,} tokens")
    print()
    print("Share the key with the user. It cannot be recovered once lost.")


def cmd_list(args):
    conn = connect(args.db)
    rows = conn.execute(
        "SELECT id, label, token_budget, tokens_used, active, created_at, last_used_at FROM api_keys ORDER BY created_at"
    ).fetchall()
    conn.close()

    if not rows:
        print("No API keys found.")
        return

    print(f"{'ID':<18} {'Label':<20} {'Budget':>10} {'Used':>10} {'Active':>7} {'Last Used'}")
    print("-" * 90)
    for row in rows:
        last = row["last_used_at"] or "never"
        active = "yes" if row["active"] else "no"
        print(
            f"{row['id']:<18} {row['label']:<20} {row['token_budget']:>10,} "
            f"{row['tokens_used']:>10,} {active:>7} {last}"
        )


def cmd_revoke(args):
    conn = connect(args.db)
    cursor = conn.execute("UPDATE api_keys SET active = 0 WHERE id = ?", (args.key_id,))
    conn.commit()
    if cursor.rowcount > 0:
        print(f"Revoked key {args.key_id}")
    else:
        print(f"Key not found: {args.key_id}")
    conn.close()


def main():
    parser = argparse.ArgumentParser(description="Artifact API key management")
    parser.add_argument(
        "--db", type=Path, default=DEFAULT_DB,
        help=f"Path to keys.sqlite (default: {DEFAULT_DB})",
    )
    sub = parser.add_subparsers(dest="command")

    create_p = sub.add_parser("create", help="Generate a new API key")
    create_p.add_argument("--label", default="", help="Label for the key")
    create_p.add_argument("--budget", type=int, default=100000, help="Token budget")

    sub.add_parser("list", help="List all API keys")

    revoke_p = sub.add_parser("revoke", help="Revoke an API key")
    revoke_p.add_argument("key_id", help="Key ID to revoke")

    args = parser.parse_args()

    if args.command == "create":
        cmd_create(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "revoke":
        cmd_revoke(args)
    else:
        parser.print_help()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
