from __future__ import annotations

import argparse
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, build_opener

try:
    from .release_identity import find_identity_leaks
except ImportError:  # Direct execution as ``python scripts/verify_release.py``.
    from release_identity import find_identity_leaks


ROOT = Path(__file__).resolve().parents[1]
SUPPORTED_PYTHON_MINORS = {(3, 12), (3, 13)}


def is_supported_python_runtime(version_info: object, pointer_bits: int) -> bool:
    """Match the 64-bit Python versions supported by install_hsptl.bat."""
    try:
        minor = tuple(version_info[:2])  # type: ignore[index]
    except (TypeError, KeyError, IndexError):
        return False
    return minor in SUPPORTED_PYTHON_MINORS and pointer_bits == 64


VENV_PYTHON = ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
PYTHON = str(VENV_PYTHON) if VENV_PYTHON.is_file() else sys.executable


def npm_command(*arguments: str) -> list[str]:
    if os.name == "nt":
        return [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", "npm.cmd", *arguments]
    return ["npm", *arguments]


def run_command(name: str, command: list[str], *, cwd: Path = ROOT) -> bool:
    print(f"\n== {name} ==")
    print("$ " + subprocess.list2cmdline(command))
    try:
        result = subprocess.run(command, cwd=cwd, check=False)
    except OSError as exc:
        print(f"FAILED: {name} ({exc})")
        return False
    if result.returncode:
        print(f"FAILED: {name} (exit {result.returncode})")
        return False
    print(f"PASS: {name}")
    return True


def check_python_environment() -> bool:
    print("\n== Python environment ==")
    command = [
        PYTHON, "-c",
        "import sys,struct; from scripts.verify_release import is_supported_python_runtime; "
        "print(sys.version.split()[0]); "
        "raise SystemExit(0 if is_supported_python_runtime(sys.version_info, struct.calcsize('P') * 8) else 2)",
    ]
    version = subprocess.run(command, cwd=ROOT, check=False)
    if version.returncode:
        print("FAIL: use 64-bit Python 3.12 or 3.13; other Python minors are not supported by this release.")
        return False
    required = ("fastapi", "uvicorn", "pandas", "requests", "pypdf", "pytest", "httpx", "jsonschema")
    check = subprocess.run(
        [PYTHON, "-c", "import importlib.util,sys; names=" + repr(required) + "; missing=[n for n in names if importlib.util.find_spec(n) is None]; print('Missing Python modules: ' + ', '.join(missing)) if missing else print('All backend and test modules are installed.'); sys.exit(bool(missing))"],
        cwd=ROOT, check=False,
    )
    if check.returncode:
        print("FAIL: run install_hsptl.bat to install runtime and test dependencies into .venv.")
        return False
    print("PASS: supported Python runtime and required modules")
    return True


def check_launcher_contracts() -> bool:
    contracts = {
        "install_hsptl.bat": ("requirements-dev.txt", "npm ci", "npm run build", "clean_venv_artifacts.py", "pip check"),
        "start_hsptl.bat": ("run_hsptl_backend.bat", "check_port.py", "HSPTL_RESOLVED_PORT", "startup_preflight.py", "HSPTL_HOME"),
        "run_hsptl_backend.bat": ("uvicorn", "127.0.0.1", "check_port.py", "HSPTL_RESOLVED_PORT"),
        "run_backend.bat": ("uvicorn", "127.0.0.1", "check_port.py"),
        "check_hsptl.bat": ("pip check", "scripts\\verify_release.py"),
        "dev_hsptl.bat": ("npm", "run_hsptl_backend.bat"),
    }
    failures: list[str] = []
    for filename, required_text in contracts.items():
        path = ROOT / filename
        if not path.is_file():
            failures.append(f"Missing launcher: {filename}")
            continue
        content = path.read_text(encoding="utf-8", errors="replace").casefold()
        missing = [item for item in required_text if item.casefold() not in content]
        if missing:
            failures.append(f"{filename} is missing expected content: {', '.join(missing)}")
    if failures:
        print("\n== Launcher contract ==")
        for failure in failures:
            print(f"FAIL: {failure}")
        return False
    print("\n== Launcher contract ==\nPASS: expected Windows launchers and commands are present")
    return True


def boot_smoke_test() -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]

    healthy = False
    with tempfile.TemporaryDirectory(
        prefix="hsptl-release-check-",
        ignore_cleanup_errors=True,
    ) as home_text:
        home = Path(home_text)
        env = os.environ.copy()
        env["HSPTL_HOME"] = str(home / "hsptl-data")
        env["WARDX_HOME"] = str(home / "legacy-wardx-source")
        env["WARDLE_HOME"] = str(home / "legacy-wardle-source")
        env["CASEDLE_HOME"] = str(home / "legacy-casedle-source")
        env.pop("SYNTHEA_CSV_DIR", None)
        current_pythonpath = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = str(ROOT) + (os.pathsep + current_pythonpath if current_pythonpath else "")
        command = [
            PYTHON, "-m", "uvicorn", "backend.main:app",
            "--host", "127.0.0.1", "--port", str(port), "--workers", "1",
            "--log-level", "warning",
        ]
        opener = build_opener(ProxyHandler({}))
        print("\n== Local backend boot ==")
        print("$ " + subprocess.list2cmdline(command))
        with tempfile.TemporaryFile(mode="w+t", encoding="utf-8") as log:
            try:
                creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
                process = subprocess.Popen(
                    command,
                    cwd=ROOT,
                    env=env,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    creationflags=creationflags,
                )
            except OSError as exc:
                print(f"FAIL: could not start backend: {exc}")
            else:
                try:
                    deadline = time.monotonic() + 25
                    while time.monotonic() < deadline:
                        if process.poll() is not None:
                            break
                        try:
                            with opener.open(f"http://127.0.0.1:{port}/api/health", timeout=1) as response:
                                if response.status == 200:
                                    print("PASS: /api/health returned HTTP 200")
                                    healthy = True
                                    break
                        except (HTTPError, URLError, TimeoutError, OSError):
                            time.sleep(0.25)
                    if not healthy:
                        log.seek(0)
                        output = log.read().strip()
                        print("FAIL: backend did not become healthy within 25 seconds")
                        if output:
                            print(output[-4000:])
                finally:
                    if process.poll() is None:
                        if os.name == "nt":
                            try:
                                process.send_signal(signal.CTRL_BREAK_EVENT)
                            except OSError:
                                process.terminate()
                        else:
                            process.terminate()
                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait()
    if home.exists():
        print(f"FAIL: temporary backend data could not be removed: {home}")
        return False
    return healthy


def main() -> int:
    parser = argparse.ArgumentParser(description="Run HSPTL release verification gates.")
    parser.add_argument("--skip-tests", action="store_true", help="Skip the full pytest suite.")
    parser.add_argument("--skip-frontend", action="store_true", help="Skip frontend typecheck and build.")
    parser.add_argument("--skip-boot", action="store_true", help="Skip the local backend health smoke test.")
    args = parser.parse_args()

    results: list[bool] = []
    results.append(check_python_environment())
    leaks = find_identity_leaks(ROOT)
    if leaks:
        print("\n== Product identity scan ==")
        for path, marker in leaks:
            print(f"FAIL: legacy identity marker in {path} ({marker})")
        results.append(False)
    else:
        print("\n== Product identity scan ==\nPASS: no prohibited legacy program references in distributable source")
        results.append(True)
    results.append(run_command(
        "Python compile",
        [PYTHON, "-m", "compileall", "-q", "backend", "scripts", "tests"],
    ))
    results.append(run_command(
        "Content pack schema and recipe validation",
        [PYTHON, "scripts/validate_content_packs.py"],
    ))
    if not args.skip_tests:
        env = os.environ.copy()
        current_pythonpath = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = str(ROOT) + (os.pathsep + current_pythonpath if current_pythonpath else "")
        print("\n== Backend tests ==")
        print("$ " + subprocess.list2cmdline([PYTHON, "-m", "pytest", "-q"]))
        test_result = subprocess.run(
            [PYTHON, "-m", "pytest", "-q"],
            cwd=ROOT,
            env=env,
            check=False,
        )
        results.append(test_result.returncode == 0)
        if test_result.returncode:
            print(f"FAILED: Backend tests (exit {test_result.returncode})")
        else:
            print("PASS: Backend tests")
    if not args.skip_frontend:
        frontend = ROOT / "frontend"
        results.append(run_command("Frontend typecheck", npm_command("run", "typecheck"), cwd=frontend))
        results.append(run_command("Frontend production build", npm_command("run", "build"), cwd=frontend))
    results.append(check_launcher_contracts())
    if not args.skip_boot:
        results.append(boot_smoke_test())

    passed = sum(results)
    failed = len(results) - passed
    print(f"\nRelease verification: {passed} passed, {failed} failed.")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
