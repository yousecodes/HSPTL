"""Resolve and probe the HSPTL loopback port for the Windows launchers.

Two jobs, both needed before the browser opens:

1. Resolve the port from `HSPTL_PORT` (default 8000) so `.bat` files never
   hardcode a number that can drift from `backend/hsptl_core/config.py`.
2. Prove the port is usable, so a clash is reported as an actionable message
   instead of a blank page plus a bare uvicorn `[Errno 10048]`.

The probe binds with SO_REUSEADDR, exactly as uvicorn does. A port left in
TIME_WAIT by a process that just exited is unbindable without that option but
starts fine with it, so probing more strictly than the server binds would
report a clash for a port that would have worked.

A failed bind on Windows has three causes with different remedies, so they are
distinguished rather than guessed at:

* Another process is listening. `netstat` names it; stop it with `taskkill`.
* Windows reserved the port range (Hyper-V, WSL2, Docker Desktop). Nothing is
  listening, so `taskkill` cannot help; pick a port outside the range.
* Something else is wrong with the bind. Report the OS error verbatim.

On success the resolved port is printed to stdout, for the launcher to capture.
"""

from __future__ import annotations

import socket
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.hsptl_core.config import (  # noqa: E402
    APP_NAME,
    DEFAULT_HOST,
    PORT_ENV_VAR,
    resolve_port,
)

# Windows reports a reserved port as WSAEACCES (10013); a port held by another
# process is WSAEADDRINUSE (10048). Only the second has a process to kill.
_WSAEACCES = 10013


class PortUnavailable(Exception):
    """The port could not be bound, with the reason kept for the message."""

    def __init__(self, detail: str, *, reserved: bool) -> None:
        super().__init__(detail)
        self.detail = detail
        self.reserved = reserved


def probe_bind(host: str, port: int) -> None:
    """Bind the port the way uvicorn will, raising `PortUnavailable` if it fails."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind((host, port))
        except OSError as exc:
            # winerror is authoritative on Windows; errno is the portable
            # fallback for POSIX hosts running this probe.
            code = getattr(exc, "winerror", None) or exc.errno
            raise PortUnavailable(
                exc.strerror or str(exc), reserved=code == _WSAEACCES
            ) from exc


def port_is_free(host: str = DEFAULT_HOST, port: int | None = None) -> bool:
    port = resolve_port() if port is None else port
    # Check for a listener first: on Windows SO_REUSEADDR can let a bind succeed
    # over an active listener, so a successful bind alone proves nothing there.
    if is_listening(host, port):
        return False
    try:
        probe_bind(host, port)
    except PortUnavailable:
        return False
    return True


def is_listening(host: str, port: int, timeout: float = 1.0) -> bool:
    """True when a socket accepts connections on the port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(timeout)
        return probe.connect_ex((host, port)) == 0


def looks_like_hsptl(host: str, port: int, timeout: float = 1.5) -> bool:
    """True when something on the port answers as HSPTL.

    Tells "you already have HSPTL open" apart from "an unrelated program took
    the port". Failing to reach it is not an error, only a "not us".
    """
    try:
        with urllib.request.urlopen(
            f"http://{host}:{port}/api/health", timeout=timeout
        ) as response:
            body = response.read(4096).decode("utf-8", "replace")
    except (urllib.error.URLError, OSError, ValueError):
        return False
    return f'"{APP_NAME}"' in body


def _clash_message(port: int, failure: PortUnavailable, *, listening: bool, is_hsptl: bool) -> str:
    if failure.reserved:
        return (
            f"HSPTL cannot start: Windows has reserved port {port}.\n"
            "\n"
            "No program is holding the port, so there is nothing to close. Windows\n"
            "reserves ranges for Hyper-V, WSL2 and Docker Desktop, and a reserved port\n"
            "cannot be bound by anything.\n"
            "\n"
            "To see the reserved ranges, run this in an Administrator terminal:\n"
            "    netsh interface ipv4 show excludedportrange protocol=tcp\n"
            "\n"
            f"Then choose a port outside them, for example {port + 1} or 8080:\n"
            f"    set {PORT_ENV_VAR}=8080\n"
            "    start_hsptl.bat\n"
        )

    if not listening:
        return (
            f"HSPTL cannot start: {DEFAULT_HOST}:{port} could not be bound.\n"
            f"    {failure.detail}\n"
            "\n"
            "No program is listening on the port, so this is not another copy of\n"
            "HSPTL. Choose a different port and try again:\n"
            f"    set {PORT_ENV_VAR}={port + 1}\n"
            "    start_hsptl.bat\n"
        )

    if is_hsptl:
        return (
            f"HSPTL is already running on {DEFAULT_HOST}:{port}.\n"
            "\n"
            "To fix this, either:\n"
            f"  1. Use the window that is already open: http://{DEFAULT_HOST}:{port}\n"
            "  2. Close it, or stop the process holding the port:\n"
            f"       netstat -ano | findstr :{port}\n"
            "       taskkill /PID <pid> /F\n"
            "  3. Run a second copy on a different port:\n"
            f"       set {PORT_ENV_VAR}={port + 1}\n"
            "       start_hsptl.bat\n"
        )

    return (
        f"HSPTL cannot start: {DEFAULT_HOST}:{port} is used by another program.\n"
        "\n"
        "Find the process with:\n"
        f"    netstat -ano | findstr :{port}\n"
        "\n"
        "Then either stop that program:\n"
        "    taskkill /PID <pid> /F\n"
        "\n"
        "or leave it alone and start HSPTL on a different port:\n"
        f"    set {PORT_ENV_VAR}={port + 1}\n"
        "    start_hsptl.bat\n"
    )


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    try:
        port = resolve_port(args[0]) if args else resolve_port()
    except ValueError as exc:
        print(f"HSPTL cannot start: {exc}", file=sys.stderr)
        print(
            f"Unset {PORT_ENV_VAR} to use the default, or set it to a free port such as 8080.",
            file=sys.stderr,
        )
        return 1

    # A listener is the definitive clash. Checking it first also covers Windows,
    # where SO_REUSEADDR can let probe_bind succeed over an active listener.
    if is_listening(DEFAULT_HOST, port):
        print(
            _clash_message(
                port,
                PortUnavailable("port is already accepting connections", reserved=False),
                listening=True,
                is_hsptl=looks_like_hsptl(DEFAULT_HOST, port),
            ),
            file=sys.stderr,
        )
        return 1

    try:
        probe_bind(DEFAULT_HOST, port)
    except PortUnavailable as failure:
        print(
            _clash_message(port, failure, listening=False, is_hsptl=False),
            file=sys.stderr,
        )
        return 1

    print(port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
