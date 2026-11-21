from scripts.verify_release import is_supported_python_runtime


def test_release_verifier_accepts_each_python_minor_supported_by_windows_installer():
    assert is_supported_python_runtime((3, 12, 9, "final", 0), 64)
    assert is_supported_python_runtime((3, 13, 5, "final", 0), 64)


def test_release_verifier_rejects_unsupported_python_minors_and_32_bit_runtime():
    assert not is_supported_python_runtime((3, 11, 9, "final", 0), 64)
    assert not is_supported_python_runtime((3, 14, 0, "final", 0), 64)
    assert not is_supported_python_runtime((3, 13, 5, "final", 0), 32)
    assert not is_supported_python_runtime((), 64)


def test_windows_launchers_are_headless_ci_compatible_and_use_crlf():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    for name in ("install_hsptl.bat", "check_hsptl.bat", "start_hsptl.bat"):
        payload = (root / name).read_bytes()
        assert b"\r\n" in payload
        assert b"\n" not in payload.replace(b"\r\n", b"")
        assert b"if not defined hsptl_no_pause pause" in payload.lower()


def test_github_windows_workflow_runs_clean_install_and_full_checks():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    workflow = (root / ".github" / "workflows" / "windows-release-check.yml").read_text(encoding="utf-8").lower()
    assert "runs-on: windows-latest" in workflow
    assert "install_hsptl.bat" in workflow
    assert "check_hsptl.bat" in workflow
    assert "python-version: \"3.13\"" in workflow
    assert "node-version: \"22.16.0\"" in workflow
