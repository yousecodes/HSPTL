from pathlib import Path

from scripts.release_identity import find_identity_leaks


def test_identity_scan_reports_retired_names_and_skips_generated_binary(tmp_path: Path):
    marker = "kli" + "nica"
    (tmp_path / "README.md").write_text(f"No {marker} branding remains.", encoding="utf-8")
    (tmp_path / "image.png").write_bytes(marker.encode("utf-8"))
    leaks = find_identity_leaks(tmp_path)
    assert len(leaks) == 1
    assert leaks[0][0] == Path("README.md")
    assert leaks[0][1] == marker


def test_identity_scan_passes_clean_source(tmp_path: Path):
    (tmp_path / "README.md").write_text("HSPTL clinical learning platform", encoding="utf-8")
    assert find_identity_leaks(tmp_path) == []


def test_identity_scan_catches_legacy_binary_filenames_and_directory_names(tmp_path: Path):
    legacy_dir = tmp_path / ("Road" + "MD")
    legacy_dir.mkdir()
    (legacy_dir / ("Kli" + "nica" + "Logo.png")).write_bytes(b"\x89PNG\r\n")
    leaks = find_identity_leaks(tmp_path)
    assert (Path("Road" + "MD"), "road" + "md") in leaks
    assert (Path("Road" + "MD") / ("Kli" + "nica" + "Logo.png"), "kli" + "nica") in leaks
