#!/usr/bin/env python3
"""Verify that all required tools and configs are in place."""
import os
import sys
import shutil
import subprocess

CHECKS = [
    ("Python", lambda: sys.version),
    ("pip", lambda: shutil.which("pip") or "NOT FOUND"),
    ("Node.js", lambda: subprocess.check_output(["node", "--version"]).decode().strip()),
    ("npm", lambda: subprocess.check_output(["npm", "--version"]).decode().strip()),
    ("Docker", lambda: subprocess.check_output(["docker", "--version"]).decode().strip()),
    ("Docker Compose", lambda: subprocess.check_output(["docker", "compose", "version"]).decode().strip()),
    (".env file", lambda: "OK" if os.path.exists(".env") else "MISSING — run: cp .env.example .env"),
    ("API deps", lambda: "OK" if os.path.exists("api/__pycache__") or _check_import("fastapi") else "MISSING — run: pip install -r api/requirements.txt"),
    ("Frontend deps", lambda: "OK" if os.path.exists("frontend/node_modules") else "MISSING — run: cd frontend && npm ci"),
    ("Pre-commit", lambda: shutil.which("pre-commit") or "NOT FOUND — run: pip install pre-commit"),
]

def _check_import(module):
    try:
        __import__(module)
        return True
    except ImportError:
        return False

def main():
    print("Manic AI — Setup Verification")
    print("=" * 50)

    all_ok = True
    for name, check in CHECKS:
        try:
            result = check()
            status = "OK" if "MISSING" not in str(result) and "NOT FOUND" not in str(result) else "WARN"
            icon = "✓" if status == "OK" else "!"
            print(f"  {icon} {name}: {result}")
            if status != "OK":
                all_ok = False
        except Exception as e:
            print(f"  ✗ {name}: ERROR — {e}")
            all_ok = False

    print()
    if all_ok:
        print("All checks passed!")
    else:
        print("Some checks need attention. See above.")

    return 0 if all_ok else 1

if __name__ == "__main__":
    sys.exit(main())
