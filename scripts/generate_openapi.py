#!/usr/bin/env python3
"""Export the Cadence OpenAPI schema to a JSON file.

Usage:
    poetry run python scripts/generate_openapi.py
    poetry run python scripts/generate_openapi.py --output docs/openapi.json
    poetry run python scripts/generate_openapi.py --pretty
"""

import argparse
import json
import sys
from pathlib import Path

# Add src to path so cadence is importable without installation
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export Cadence OpenAPI schema to a JSON file"
    )
    parser.add_argument(
        "--output",
        "-o",
        default="openapi_schema.json",
        help="Output file path (default: scripts/openapi_schema.json)",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        default=True,
        help="Pretty-print JSON with indentation (default: true)",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Write compact JSON without indentation",
    )
    args = parser.parse_args()

    indent = None if args.compact else 2

    print("=== Cadence OpenAPI Schema Export ===\n")

    try:
        print("1. Loading application...")
        from cadence.main import app  # noqa: PLC0415

        print("   ✓ Application loaded")

        print("2. Generating OpenAPI schema...")
        schema = app.openapi()
        info = schema.get("info", {})
        print(f"   ✓ Title:   {info.get('title', 'N/A')}")
        print(f"   ✓ Version: {info.get('version', 'N/A')}")
        print(f"   ✓ Paths:   {len(schema.get('paths', {}))}")

        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        print(f"3. Writing to {output_path}...")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(schema, f, indent=indent, ensure_ascii=False)
            f.write("\n")

        size_kb = output_path.stat().st_size / 1024
        print(f"   ✓ Written ({size_kb:.1f} KB)")

        print(f"\n✓ OpenAPI schema exported to: {output_path}")
        print("\nView interactive docs when the server is running:")
        print("  Swagger UI  http://localhost:8000/docs")
        print("  ReDoc       http://localhost:8000/redoc")
        print("  Raw JSON    http://localhost:8000/openapi.json")

    except ImportError as e:
        print(f"\n✗ Import error: {e}")
        print("  Make sure dependencies are installed: poetry install")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
