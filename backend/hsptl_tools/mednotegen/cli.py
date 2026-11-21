from __future__ import annotations
import argparse
from pathlib import Path
from .fhir import load_fhir_directory
from .narratives import build_outputs
from .exporters import export_json, export_markdown

def main(argv=None):
    parser=argparse.ArgumentParser(description="Transform Synthea FHIR exports into traceable HSPTL Clinic narratives and Pearls learning seeds.")
    parser.add_argument("--fhir-dir", required=True, help="Directory containing Synthea FHIR JSON files")
    parser.add_argument("--output", required=True, help="Output directory")
    parser.add_argument("--format", choices=["json","markdown","both"], default="both")
    args=parser.parse_args(argv)
    resources, errors=load_fhir_directory(args.fhir_dir)
    payload=build_outputs(resources)
    out=Path(args.output); out.mkdir(parents=True,exist_ok=True)
    if args.format in ("json","both"):
        export_json(payload,out/"hsptl_import.json")
    if args.format in ("markdown","both"):
        export_markdown(payload,out/"documents")
    print(f"Loaded {len(resources)} FHIR resources; created {len(payload['clinic_cases'])} Clinic case narratives and {len(payload['pearl_seeds'])} draft Pearl seeds.")
    if errors:
        print(f"Warning: {len(errors)} file(s) could not be parsed:")
        for error in errors[:10]: print(f"- {error}")
    return payload

if __name__ == "__main__": main()
