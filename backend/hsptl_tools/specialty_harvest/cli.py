"""Backward-compatible command-line entry point for the Clinical Knowledge Harvester."""
from __future__ import annotations
from . import engine as _engine

CASE_REPORT_JOURNALS = getattr(_engine, 'CASE_REPORT_JOURNALS')
HERE = getattr(_engine, 'HERE')
Path = getattr(_engine, 'Path')
SOURCE_PRESETS = getattr(_engine, 'SOURCE_PRESETS')
SPECIALTIES = getattr(_engine, 'SPECIALTIES')
_load_caches = getattr(_engine, '_load_caches')
_save_caches = getattr(_engine, '_save_caches')
argparse = getattr(_engine, 'argparse')
existing_ids = getattr(_engine, 'existing_ids')
harvest_specialty = getattr(_engine, 'harvest_specialty')
os = getattr(_engine, 'os')
subprocess = getattr(_engine, 'subprocess')
sys = getattr(_engine, 'sys')

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", nargs="+", metavar="KEY")
    ap.add_argument("--knowledge-profile", choices=["case_reports", "guidelines", "systematic_reviews", "trials", "observational", "clinical_evidence", "all_open_access"], default="case_reports", help="clinical knowledge class to harvest; case_reports preserves the legacy default")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--list-journals", action="store_true")
    ap.add_argument("--count", action="store_true")
    ap.add_argument("--per-specialty", type=int, default=0)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--sources", nargs="+", default=["exam"],
                    choices=["exam", "minimal", "wide", "all",
                             "europepmc", "pubmed", "pmc", "journals", "doaj", "crossref"],
                    help="source preset (default: exam journals)")
    ap.add_argument("--journals", nargs="+", default=list(CASE_REPORT_JOURNALS),
                    choices=list(CASE_REPORT_JOURNALS))
    ap.add_argument("--journal-workers", type=int, default=12)
    ap.add_argument("--exam-max", type=int, default=40)
    ap.add_argument("--journals-max-per-journal", type=int, default=200,
                    help="cap Crossref results per journal; 0 = skip Crossref entirely")
    ap.add_argument("--max-per-source", type=int, default=0)
    ap.add_argument("--ncbi-api-key", default=os.environ.get("NCBI_API_KEY", ""))
    ap.add_argument("--unpaywall-email", default=os.environ.get("UNPAYWALL_EMAIL", ""))
    ap.add_argument("--no-pmc-fallback", action="store_true")
    ap.add_argument("--no-convert", action="store_true")
    ap.add_argument("--no-batch", action="store_true")
    ap.add_argument("--batch-size", type=int, default=200)
    ap.add_argument("--pmc-broad", action="store_true")
    ap.add_argument("--fast", action="store_true")
    ap.add_argument("--journal-mode", choices=["all", "exam-only", "important", "skip"], default="all",
                    help="all: include all journal articles; exam-only: only exam-titled journal articles; skip: no journals")
    ap.add_argument("--journal-min-score", type=int, default=2,
                    help="minimum importance score for --journal-mode important (2=moderate, 3=strict, 4=very strict)")
    ap.add_argument("--year-from", type=int)
    ap.add_argument("--year-to", type=int)
    ap.add_argument("--out", default="specialties")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--pmc-workers", type=int, default=4,
                    help="parallel PMC downloads (default 4; lower if rate-limited)")
    ap.add_argument("--delay", type=float, default=0.05)
    ap.add_argument("--audit", action="store_true")
    ap.add_argument("--clean", action="store_true")
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--chunk", type=int, default=500)
    args = ap.parse_args(argv)

    if args.fast:
        args.workers = 16
        args.delay = 0.02

    if len(args.sources) == 1 and args.sources[0] in SOURCE_PRESETS:
        args.sources = list(SOURCE_PRESETS[args.sources[0]])
    if getattr(args, "journal_mode", "all") == "skip" and "journals" in args.sources:
        args.sources = [s for s in args.sources if s != "journals"]
        if not args.sources:
            args.sources = ["exam", "examtitle"]

    _engine.NCBI_API_KEY = args.ncbi_api_key
    _engine.configure_ncbi_api_key(args.ncbi_api_key)
    _engine._PMC_BROAD = args.pmc_broad

    _load_caches()

    if args.list:
        for k, v in SPECIALTIES.items():
            print(k.ljust(18) + " " + v[0])
        return
    if args.list_journals:
        for k, (display, pmc_name, issn, _prefix) in CASE_REPORT_JOURNALS.items():
            print(k.ljust(26) + " " + display.ljust(58) + " ISSN " + issn)
        return
    if args.all:
        args.per_specialty = 0
    keys = args.only or list(SPECIALTIES)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    claimed = existing_ids(out)
    total = 0
    for k in keys:
        print("\n=== " + SPECIALTIES[k][0] + " ===")
        try:
            n, _ = harvest_specialty(k, args, out, claimed)
        except Exception as e:
            print("  FAILED: " + str(e) + "\n")
            continue
        total += n
        if args.build and n:
            Path("decks").mkdir(exist_ok=True)
            subprocess.call([sys.executable, str(HERE / "cases2anki.py"), str(out / k),
                             "-o", "decks/" + k + ".apkg",
                             "--deck", "Case Reports::" + SPECIALTIES[k][0],
                             "--specialty", k, "--text-only",
                             "--chunk", str(args.chunk)])
    _save_caches()
    print("\nDone: " + str(total) + " cases in " + str(out) + "/")

