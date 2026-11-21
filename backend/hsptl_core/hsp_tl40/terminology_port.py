"""Embedded exact-match terminology index with an optional Snowstorm ECL port."""
from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

from .kernel import EventKernel


EMBEDDED_CONCEPTS: dict[str, dict[str, Any]] = {
    "LOINC: vital-signs": {"code": "85353-1", "system": "http://loinc.org", "display": "Vital signs panel", "aliases": ["vitals"]},
    "SNOMED: dyspnoea": {"code": "267036007", "system": "http://snomed.info/sct", "display": "Dyspnoea", "aliases": ["dyspnea", "shortness of breath"]},
    "SNOMED: chest pain": {"code": "29857009", "system": "http://snomed.info/sct", "display": "Chest pain", "aliases": []},
}


class TerminologyPort:
    def __init__(self, snowstorm_url: str | None = None, db_path: Path | str | None = None,
                 kernel: EventKernel | None = None):
        self.snowstorm_url = snowstorm_url.strip() if snowstorm_url else ""
        self.db_path = Path(db_path) if db_path else None
        self.kernel = kernel
        if self.db_path:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            with self._connect() as conn:
                conn.executescript("""
                    CREATE TABLE IF NOT EXISTS hsptl_snomed_concepts (
                        concept_id TEXT PRIMARY KEY, effective_time TEXT NOT NULL,
                        active INTEGER NOT NULL, module_id TEXT NOT NULL, definition_status_id TEXT NOT NULL,
                        release_id TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS hsptl_snomed_descriptions (
                        description_id TEXT PRIMARY KEY, concept_id TEXT NOT NULL,
                        effective_time TEXT NOT NULL, active INTEGER NOT NULL,
                        language_code TEXT NOT NULL, type_id TEXT NOT NULL, term TEXT NOT NULL,
                        case_significance_id TEXT NOT NULL, release_id TEXT NOT NULL,
                        FOREIGN KEY(concept_id) REFERENCES hsptl_snomed_concepts(concept_id)
                    );
                    CREATE INDEX IF NOT EXISTS hsptl_snomed_term_idx ON hsptl_snomed_descriptions(term COLLATE NOCASE);
                    CREATE INDEX IF NOT EXISTS hsptl_snomed_concept_idx ON hsptl_snomed_descriptions(concept_id);
                    CREATE INDEX IF NOT EXISTS hsptl_snomed_release_idx ON hsptl_snomed_descriptions(release_id, effective_time);
                    CREATE TABLE IF NOT EXISTS hsptl_snomed_imports (
                        release_id TEXT PRIMARY KEY, edition TEXT NOT NULL, effective_time TEXT NOT NULL,
                        concepts INTEGER NOT NULL, descriptions INTEGER NOT NULL,
                        file_hashes_json TEXT NOT NULL
                    );
                """)

    def _connect(self):
        if self.db_path is None:
            raise RuntimeError("No embedded terminology database is configured.")
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=30000")
        return conn

    def lookup(self, term: str) -> dict[str, Any]:
        key = term.strip()
        if not key:
            return {"state": "abstain", "reason": "An exact concept term or identifier is required."}
        if self.db_path:
            with self._connect() as conn:
                concept = conn.execute(
                    "SELECT * FROM hsptl_snomed_concepts WHERE concept_id=? AND active=1 ORDER BY effective_time DESC LIMIT 1",
                    (key,),
                ).fetchone()
                if concept:
                    description = conn.execute(
                        "SELECT term,type_id,language_code FROM hsptl_snomed_descriptions WHERE concept_id=? AND active=1 ORDER BY CASE WHEN type_id='900000000000003001' THEN 0 ELSE 1 END, effective_time DESC, term LIMIT 1",
                        (key,),
                    ).fetchone()
                    return {"state": "pass", "concept": {"code": concept[0],
                        "system": "http://snomed.info/sct", "display": description[0] if description else key,
                        "language": description[2] if description else None,
                        "module_id": concept[3], "effective_time": concept[1]},
                        "source": "embedded_snomed_rf2_index"}
                row = conn.execute(
                    "SELECT d.concept_id,d.term,d.language_code,c.effective_time FROM hsptl_snomed_descriptions d JOIN hsptl_snomed_concepts c ON c.concept_id=d.concept_id WHERE d.active=1 AND c.active=1 AND d.term=? COLLATE NOCASE ORDER BY d.effective_time DESC LIMIT 1",
                    (key,),
                ).fetchone()
                if row:
                    return {"state": "pass", "concept": {"code": row[0],
                        "system": "http://snomed.info/sct", "display": row[1],
                        "language": row[2], "effective_time": row[3]},
                        "source": "embedded_snomed_rf2_index"}
        folded = key.casefold()
        for item in EMBEDDED_CONCEPTS.values():
            if folded == item["display"].casefold() or folded in [alias.casefold() for alias in item["aliases"]] or folded == item["code"].casefold():
                return {"state": "pass", "concept": item, "source": "embedded_concept_index"}
        return {"state": "abstain", "reason": "No exact embedded terminology match; no approximate concept mapping is performed."}

    @staticmethod
    def _find_rf2_file(directory: Path, prefix: str) -> Path:
        matches = sorted(directory.glob(f"{prefix}*Snapshot*.txt"))
        if not matches:
            matches = sorted(directory.glob(f"{prefix}*.txt"))
        if len(matches) != 1:
            raise ValueError(f"Expected exactly one RF2 file for {prefix}; found {len(matches)}.")
        return matches[0]

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def import_snomed_rf2(self, directory: Path | str, *, edition: str,
                          effective_time: str, licensed_use_confirmed: bool = False) -> dict[str, Any]:
        """Index a locally supplied SNOMED CT RF2 snapshot after explicit licence confirmation.

        No SNOMED CT content is bundled. The source must be a lawfully obtained
        local RF2 snapshot. This importer loads active concepts and descriptions;
        it does not implement ECL or infer clinical meaning from relationships.
        """
        if not self.db_path:
            raise ValueError("RF2 import requires an embedded terminology database path.")
        if not licensed_use_confirmed:
            raise PermissionError("Confirm that the organization is entitled to use this SNOMED CT edition before import.")
        if not edition.strip() or not effective_time.strip():
            raise ValueError("Edition and effective_time are required for terminology provenance.")
        root = Path(directory)
        if not root.is_dir():
            raise ValueError("RF2 input directory does not exist.")
        concept_file = self._find_rf2_file(root, "sct2_Concept_")
        description_file = self._find_rf2_file(root, "sct2_Description_")
        file_hashes = {concept_file.name: self._sha256(concept_file),
                       description_file.name: self._sha256(description_file)}
        release_id = f"{edition}:{effective_time}:{file_hashes[concept_file.name][:12]}"

        concepts: list[tuple[str, str, int, str, str, str]] = []
        active_ids: set[str] = set()
        with concept_file.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream, delimiter="\t")
            required = {"id", "effectiveTime", "active", "moduleId", "definitionStatusId"}
            if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
                raise ValueError("RF2 Concept file has an unsupported column header.")
            for row in reader:
                active = int(row["active"])
                concepts.append((row["id"], row["effectiveTime"], active, row["moduleId"],
                                 row["definitionStatusId"], release_id))
                if active == 1:
                    active_ids.add(row["id"])

        descriptions: list[tuple[str, str, str, int, str, str, str, str, str]] = []
        with description_file.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream, delimiter="\t")
            required = {"id", "effectiveTime", "active", "moduleId", "conceptId", "languageCode", "typeId", "term", "caseSignificanceId"}
            if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
                raise ValueError("RF2 Description file has an unsupported column header.")
            for row in reader:
                if row["conceptId"] not in active_ids:
                    continue
                descriptions.append((row["id"], row["conceptId"], row["effectiveTime"],
                    int(row["active"]), row["languageCode"], row["typeId"], row["term"],
                    row["caseSignificanceId"], release_id))

        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.executemany("INSERT OR REPLACE INTO hsptl_snomed_concepts VALUES(?,?,?,?,?,?)", concepts)
            conn.executemany("INSERT OR REPLACE INTO hsptl_snomed_descriptions VALUES(?,?,?,?,?,?,?,?,?)", descriptions)
            conn.execute("INSERT OR REPLACE INTO hsptl_snomed_imports VALUES(?,?,?,?,?,?)",
                (release_id, edition, effective_time, len(active_ids), len(descriptions),
                 json.dumps(file_hashes, sort_keys=True)))

        result = {"state": "pass", "release_id": release_id, "edition": edition,
                  "effective_time": effective_time, "concept_count": len(active_ids),
                  "description_count": len(descriptions), "file_hashes": file_hashes,
                  "index": "embedded_sqlite", "ecl": "not_supported_by_embedded_index"}
        if self.kernel:
            result["event"] = self.kernel.append("platform.terminology.imported", {
                "edition": edition, "effective_time": effective_time,
                "concept_count": len(active_ids), "description_count": len(descriptions),
                "file_hashes": file_hashes, "release_id": release_id,
            })
        return result

    def query_ecl(self, expression: str) -> dict[str, Any]:
        if not self.snowstorm_url:
            return {"state": "abstain", "reason": "Full ECL requires a configured Snowstorm port.",
                    "expression": expression}
        return {"state": "abstain", "reason": "Snowstorm transport adapter is an external port and has not been configured by this package.",
                "expression": expression, "endpoint_configured": True}
