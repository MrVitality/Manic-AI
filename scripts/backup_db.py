#!/usr/bin/env python3
"""Automated database backup using pg_dump.

Usage:
    python scripts/backup_db.py                    # Backup to backups/ directory
    python scripts/backup_db.py --output /path/    # Custom output directory
    python scripts/backup_db.py --retain 7         # Keep last 7 backups (default)
    python scripts/backup_db.py --schemas rag      # Backup only specific schemas
"""
import argparse
import os
import stat
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent


def main():
    parser = argparse.ArgumentParser(description="Backup Manic AI database")
    parser.add_argument("--output", default=str(ROOT / "backups"), help="Backup directory")
    parser.add_argument("--retain", type=int, default=7, help="Number of backups to keep")
    parser.add_argument(
        "--schemas",
        nargs="*",
        default=["public", "rag"],
        help="Schemas to backup",
    )
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Read DB connection from environment or .env file
    db_url = os.getenv("SUPABASE_DB_URL", "")
    pg_password = ""
    if not db_url:
        env_file = ROOT / ".env"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.startswith("POSTGRES_PASSWORD="):
                    pg_password = line.split("=", 1)[1].strip()
                    db_url = f"postgresql://postgres@localhost:5433/postgres"
                    break

    if not db_url:
        print(
            "Error: No database URL found. "
            "Set SUPABASE_DB_URL or POSTGRES_PASSWORD in .env"
        )
        sys.exit(1)

    # Extract password from URL so it's not visible in process listings
    from urllib.parse import urlparse, urlunparse
    parsed = urlparse(db_url)
    if parsed.password:
        pg_password = parsed.password
        netloc = parsed.hostname or ""
        if parsed.port:
            netloc = f"{netloc}:{parsed.port}"
        if parsed.username:
            netloc = f"{parsed.username}@{netloc}"
        db_url = urlunparse(parsed._replace(netloc=netloc))

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = output_dir / f"manic_ai_backup_{timestamp}.sql.gz"

    # Build schema filter args
    schema_args: list[str] = []
    for schema in args.schemas:
        schema_args.extend(["-n", schema])

    cmd = [
        "pg_dump",
        db_url,
        "--no-owner",
        "--no-privileges",
        *schema_args,
    ]

    print(f"Backing up to {backup_file}...")
    start = time.time()

    # Pass password via a temporary .pgpass file (mode 0o600) instead of the
    # PGPASSWORD environment variable, which is visible to all processes on the
    # host via /proc/<pid>/environ.
    pgpass_file = None
    dump_env = None
    if pg_password:
        parsed_for_pgpass = __import__("urllib.parse", fromlist=["urlparse"]).urlparse(
            os.getenv("SUPABASE_DB_URL", db_url)
        )
        host = parsed_for_pgpass.hostname or "localhost"
        port = parsed_for_pgpass.port or 5432
        user = parsed_for_pgpass.username or "postgres"
        dbname = (parsed_for_pgpass.path or "/postgres").lstrip("/") or "postgres"
        pgpass_fd, pgpass_path = tempfile.mkstemp(prefix="pgpass_", suffix=".conf")
        try:
            os.write(pgpass_fd, f"{host}:{port}:{dbname}:{user}:{pg_password}\n".encode())
        finally:
            os.close(pgpass_fd)
        os.chmod(pgpass_path, stat.S_IRUSR | stat.S_IWUSR)  # 0o600
        pgpass_file = pgpass_path
        dump_env = {**os.environ, "PGPASSFILE": pgpass_path}
        # Ensure PGPASSWORD is not inadvertently inherited
        dump_env.pop("PGPASSWORD", None)

    try:
        with open(backup_file, "wb") as f:
            dump = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=dump_env)
            gzip_proc = subprocess.Popen(["gzip"], stdin=dump.stdout, stdout=f)
            dump.stdout.close()  # type: ignore[union-attr]
            gzip_proc.communicate()

            if dump.wait() != 0:
                stderr = dump.stderr.read().decode()  # type: ignore[union-attr]
                print(f"Error: pg_dump failed: {stderr}")
                backup_file.unlink(missing_ok=True)
                sys.exit(1)

    except FileNotFoundError:
        # pg_dump not available locally — fall back to Docker
        print("pg_dump not found locally, trying via Docker...")
        docker_cmd = [
            "docker",
            "exec",
            "ai-supabase-db",
            "pg_dump",
            "-U",
            "postgres",
            "--no-owner",
            "--no-privileges",
            *schema_args,
            "postgres",
        ]
        result = subprocess.run(docker_cmd, capture_output=True)
        if result.returncode != 0:
            print(f"Error: {result.stderr.decode()}")
            sys.exit(1)

        import gzip as gz

        with gz.open(backup_file, "wb") as f:
            f.write(result.stdout)

    finally:
        # Always remove the temporary .pgpass file so the password is not left on disk
        if pgpass_file and os.path.exists(pgpass_file):
            os.unlink(pgpass_file)

    elapsed = time.time() - start
    size_mb = backup_file.stat().st_size / (1024 * 1024)
    print(f"Backup complete: {backup_file} ({size_mb:.1f} MB, {elapsed:.1f}s)")

    # Prune old backups beyond retention limit
    backups = sorted(output_dir.glob("manic_ai_backup_*.sql.gz"))
    if len(backups) > args.retain:
        for old in backups[: -args.retain]:
            old.unlink()
            print(f"Removed old backup: {old.name}")

    retained = min(len(backups), args.retain)
    print(f"Backups retained: {retained}")


if __name__ == "__main__":
    main()
