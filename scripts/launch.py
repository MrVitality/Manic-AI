#!/usr/bin/env python3
"""Manic AI — Master Build & Launch Script

Orchestrates the complete setup and launch of all Manic AI services.

Usage:
    python scripts/launch.py              # Full build + launch
    python scripts/launch.py --dev        # Development mode (hot-reload)
    python scripts/launch.py --build-only # Build containers without starting
    python scripts/launch.py --status     # Show service status
    python scripts/launch.py --stop       # Stop all services
    python scripts/launch.py --monitoring # Include monitoring stack
    python scripts/launch.py --clean      # Stop + remove volumes (destructive)
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

# Project root
ROOT = Path(__file__).parent.parent
os.chdir(ROOT)

# ANSI colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def log(msg, color=GREEN):
    print(f"{color}{BOLD}>{RESET} {msg}")


def error(msg):
    print(f"{RED}{BOLD}x{RESET} {msg}")


def success(msg):
    print(f"{GREEN}{BOLD}✓{RESET} {msg}")


def header(msg):
    print(f"\n{CYAN}{BOLD}{'=' * 60}{RESET}")
    print(f"{CYAN}{BOLD}  {msg}{RESET}")
    print(f"{CYAN}{BOLD}{'=' * 60}{RESET}\n")


def run(cmd, check=True, capture=False, **kwargs):
    """Run a shell command."""
    if isinstance(cmd, str):
        cmd = cmd.split()
    try:
        result = subprocess.run(cmd, check=check, capture_output=capture, text=True, **kwargs)
        return result
    except subprocess.CalledProcessError as e:
        if capture:
            error(f"Command failed: {' '.join(cmd)}")
            if e.stderr:
                print(e.stderr)
        raise
    except FileNotFoundError:
        error(f"Command not found: {cmd[0]}")
        sys.exit(1)


def check_prerequisites():
    """Verify all required tools are installed."""
    header("Checking Prerequisites")

    checks = [
        ("Python", ["python", "--version"]),
        ("Docker", ["docker", "--version"]),
        ("Docker Compose", ["docker", "compose", "version"]),
        ("Node.js", ["node", "--version"]),
        ("npm", ["npm", "--version"]),
    ]

    all_ok = True
    for name, cmd in checks:
        try:
            result = run(cmd, capture=True)
            version = result.stdout.strip().split("\n")[0]
            success(f"{name}: {version}")
        except (subprocess.CalledProcessError, FileNotFoundError):
            error(f"{name}: NOT FOUND")
            all_ok = False

    if not all_ok:
        error("Missing prerequisites. Install them and retry.")
        sys.exit(1)


def check_env():
    """Check .env file exists and has required values."""
    header("Checking Environment")

    env_file = ROOT / ".env"
    example_file = ROOT / ".env.example"

    if not env_file.exists():
        if example_file.exists():
            log("Creating .env from .env.example...")
            shutil.copy(example_file, env_file)
            log(f"Created {env_file} — {YELLOW}fill in required values before proceeding{RESET}")
        else:
            error(".env.example not found!")
            sys.exit(1)

    # Check for required but empty values
    required = ["POSTGRES_PASSWORD", "ANON_KEY", "SERVICE_ROLE_KEY"]
    with open(env_file) as f:
        env_content = f.read()

    missing = []
    for var in required:
        for line in env_content.split("\n"):
            if line.startswith(f"{var}=") and line.strip() == f"{var}=":
                missing.append(var)

    if missing:
        log(f"{YELLOW}Warning: These required variables are empty in .env:{RESET}")
        for var in missing:
            print(f"    {YELLOW}- {var}{RESET}")
        print()
    else:
        success(".env configured")


def install_deps():
    """Install Python and Node dependencies."""
    header("Installing Dependencies")

    # Python
    log("Installing Python dependencies...")
    run(["pip", "install", "-r", "api/requirements.txt", "-q"])
    success("Python deps installed")

    # Node
    log("Installing Node dependencies...")
    run(["npm", "ci", "--legacy-peer-deps"], cwd=ROOT / "frontend")
    success("Node deps installed")


def build_containers(monitoring=False):
    """Build Docker containers."""
    header("Building Containers")

    cmd = ["docker", "compose", "build"]
    log("Building API + Frontend containers...")
    run(cmd)
    success("Containers built")


def start_services(dev=False, monitoring=False):
    """Start all services."""
    header("Starting Services")

    if dev:
        cmd = ["docker", "compose", "-f", "docker-compose.yml", "-f", "docker-compose.dev.yml", "up", "-d"]
        log("Starting in development mode (hot-reload)...")
    else:
        cmd = ["docker", "compose", "up", "-d"]
        log("Starting production services...")

    if monitoring:
        cmd.insert(-1, "--profile")
        cmd.insert(-1, "monitoring")
        log("Including monitoring stack (Prometheus + Grafana)...")

    run(cmd)
    success("Services started")


def setup_qdrant():
    """Initialize Qdrant collections."""
    header("Setting Up Qdrant")

    log("Waiting for Qdrant to be healthy...")
    for i in range(30):
        try:
            import requests
            resp = requests.get("http://localhost:6333/health", timeout=2)
            if resp.status_code == 200:
                break
        except Exception:
            pass
        time.sleep(2)
    else:
        log(f"{YELLOW}Qdrant not responding — skipping collection setup{RESET}")
        return

    log("Creating Qdrant collections...")
    run(["python", "scripts/setup_qdrant.py"])
    success("Qdrant collections ready")


def show_status():
    """Show service status."""
    header("Service Status")
    run(["docker", "compose", "ps"])


def show_urls(monitoring=False):
    """Display service URLs."""
    header("Service URLs")

    urls = [
        ("Frontend",   "http://localhost:3000"),
        ("API",        "http://localhost:8081"),
        ("API Docs",   "http://localhost:8081/docs"),
        ("Open WebUI", "http://localhost:3006"),
        ("Supabase",   "http://localhost:3005"),
        ("n8n",        "http://localhost:5679"),
        ("Langfuse",   "http://localhost:3007"),
        ("Flowise",    "http://localhost:3008"),
        ("Qdrant",     "http://localhost:6333/dashboard"),
        ("SearXNG",    "http://localhost:8889"),
    ]

    if monitoring:
        urls.extend([
            ("Prometheus", "http://localhost:9090"),
            ("Grafana",    "http://localhost:3009"),
        ])

    for name, url in urls:
        print(f"  {CYAN}-{RESET} {name:15s} -> {url}")
    print()


def stop_services():
    """Stop all services."""
    header("Stopping Services")
    run(["docker", "compose", "down"])
    success("All services stopped")


def clean_all():
    """Stop services and remove all volumes."""
    header("Cleaning Everything")
    log(f"{RED}This will delete all data volumes!{RESET}")
    confirm = input("Are you sure? (yes/no): ")
    if confirm.lower() != "yes":
        log("Cancelled")
        return
    run(["docker", "compose", "down", "-v", "--remove-orphans"])
    success("All services stopped and volumes removed")


def run_tests():
    """Run the test suite."""
    header("Running Tests")
    result = run(["python", "-m", "pytest", "api/tests/", "-q", "--tb=short"], check=False)
    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser(
        description="Manic AI — Master Build & Launch Script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--dev", action="store_true", help="Development mode with hot-reload")
    parser.add_argument("--build-only", action="store_true", help="Build without starting")
    parser.add_argument("--status", action="store_true", help="Show service status")
    parser.add_argument("--stop", action="store_true", help="Stop all services")
    parser.add_argument("--clean", action="store_true", help="Stop + remove volumes (destructive)")
    parser.add_argument("--monitoring", action="store_true", help="Include monitoring stack")
    parser.add_argument("--skip-deps", action="store_true", help="Skip dependency installation")
    parser.add_argument("--skip-tests", action="store_true", help="Skip test suite")
    parser.add_argument("--skip-qdrant", action="store_true", help="Skip Qdrant setup")
    args = parser.parse_args()

    print(f"\n{BOLD}Manic AI — Build & Launch{RESET}\n")

    # Quick actions
    if args.status:
        show_status()
        show_urls(args.monitoring)
        return

    if args.stop:
        stop_services()
        return

    if args.clean:
        clean_all()
        return

    # Full build flow
    start = time.time()

    check_prerequisites()
    check_env()

    if not args.skip_deps:
        install_deps()

    if not args.skip_tests:
        if not run_tests():
            error("Tests failed! Fix issues before deploying.")
            log(f"{YELLOW}Use --skip-tests to bypass{RESET}")
            sys.exit(1)

    build_containers(monitoring=args.monitoring)

    if args.build_only:
        success("Build complete (not started)")
        return

    start_services(dev=args.dev, monitoring=args.monitoring)

    if not args.skip_qdrant:
        setup_qdrant()

    elapsed = time.time() - start

    header("Launch Complete!")
    print(f"  Total time: {elapsed:.0f}s")
    print()
    show_urls(args.monitoring)

    success(f"Manic AI is running! Open {CYAN}http://localhost:3000{RESET}")


if __name__ == "__main__":
    main()
