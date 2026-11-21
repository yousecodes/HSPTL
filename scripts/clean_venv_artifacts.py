"""Remove only pip's known interrupted-upgrade residue inside HSPTL .venv."""
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
venv = (root / '.venv').resolve()
if not venv.is_dir():
    raise SystemExit(0)
removed = []
for site in venv.glob('Lib/site-packages'):
    for item in site.iterdir():
        # pip leaves these temporary names after an interrupted Windows upgrade.
        if item.name.startswith('~ip') and (item.name.endswith('.dist-info') or item.name in {'~ip','~ip.exe','~ip3.exe'}):
            try:
                if item.is_dir():
                    import shutil; shutil.rmtree(item)
                else:
                    item.unlink()
                removed.append(item.name)
            except OSError as exc:
                print(f'WARNING: could not remove stale pip artifact {item.name}: {exc}', file=sys.stderr)
if removed:
    print('Removed interrupted pip-upgrade residue: ' + ', '.join(removed))
