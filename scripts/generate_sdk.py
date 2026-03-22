#!/usr/bin/env python3
"""Generate TypeScript SDK from the FastAPI OpenAPI schema.

Usage:
    python scripts/generate_sdk.py [--output frontend/lib/generated-api.ts]

Exports the OpenAPI JSON spec and optionally generates a TypeScript client
using openapi-typescript if installed.
"""
import json
import sys
import subprocess
from pathlib import Path

def main():
    output_dir = Path("frontend/lib")
    spec_path = output_dir / "openapi.json"
    types_path = output_dir / "api-types.ts"

    # Import the FastAPI app to extract the OpenAPI schema
    sys.path.insert(0, ".")
    from api.app import app

    schema = app.openapi()

    # Write the spec
    spec_path.write_text(json.dumps(schema, indent=2))
    print(f"OpenAPI spec written to {spec_path}")

    # Try to generate TypeScript types using openapi-typescript
    try:
        result = subprocess.run(
            ["npx", "openapi-typescript", str(spec_path), "-o", str(types_path)],
            capture_output=True, text=True, cwd=".", timeout=30
        )
        if result.returncode == 0:
            print(f"TypeScript types written to {types_path}")
        else:
            print(f"openapi-typescript failed: {result.stderr}")
            print("Install with: npm install -D openapi-typescript")
    except FileNotFoundError:
        print("npx not found — skipping TypeScript generation")
        print("Install Node.js and run: npm install -D openapi-typescript")
    except subprocess.TimeoutExpired:
        print("TypeScript generation timed out")

if __name__ == "__main__":
    main()
