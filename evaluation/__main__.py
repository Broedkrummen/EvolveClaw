import argparse
import json
from pathlib import Path

from .runner import run_pilot
from .scenarios import planned_manifest, validate_manifest
from .storage_smoke import run_storage_smoke


def main():
    parser = argparse.ArgumentParser(description="Offline EvolveClaw mechanics simulations. No efficacy evidence.")
    sub = parser.add_subparsers(dest="command", required=True)
    pilot = sub.add_parser("pilot", help="Run 20 scripted sequences across 3 isolated conditions; no model calls")
    pilot.add_argument("--output", required=True, type=Path, help="New output directory; existing directories are never overwritten")
    manifest = sub.add_parser("manifest", help="Export authored pilot and planned development/held-out authoring slots")
    manifest.add_argument("--output", required=True, type=Path)
    storage = sub.add_parser("storage-smoke", help="Check actual MemoryStore with authored lessons in isolated data; no models")
    storage.add_argument("--output", required=True, type=Path)
    reference = sub.add_parser("scope-reference-smoke", help="Direct upstream SCOPE 0.1.3 defaults with injected offline responses")
    reference.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.command == "pilot":
        result = run_pilot(args.output)
        print(json.dumps({"evidence_kind": result["evidence_kind"], "surrogate": True,
                          "efficacy_evidence": False, "authored_sequences": result["authored_sequences"],
                          "family_clusters": result["family_clusters"], "sequence_runs": result["sequence_runs"],
                          "model_calls": 0, "output": str(args.output.resolve())}, indent=2))
    elif args.command == "storage-smoke":
        print(json.dumps(run_storage_smoke(args.output), indent=2))
    elif args.command == "scope-reference-smoke":
        import asyncio
        from .scope_reference import run_reference_smoke
        result = asyncio.run(run_reference_smoke(args.output))
        print(json.dumps({key: result[key] for key in (
            "condition", "sdk_version", "actual_upstream_optimizer", "scripted_model",
            "evidence_kind", "task_quality_measured", "scripted_generate_calls", "live_api_calls", "checks")}, indent=2))
    else:
        rows = planned_manifest()
        validate_manifest(rows)
        with args.output.open("x") as output:
            json.dump({"schema_version": 1, "sequences": rows}, output, indent=2)
            output.write("\n")
        print("Exported authoring manifest. Only pilot rows have executable fixtures.")


if __name__ == "__main__":
    main()
