"""Modular Specialty Harvest package with backwards-compatible public exports."""
from .engine import (
    SPECIALTIES, Candidate, SourceAdapter, EuropePMCSource, PMCOASource,
    DOAJSource, CrossrefSource, PubMedSource, JournalSource, ExamCuratedSource,
    extract_jats_license, is_valid_specialty_case, query_for, main,
)

__all__ = [
    "SPECIALTIES", "Candidate", "SourceAdapter", "EuropePMCSource",
    "PMCOASource", "DOAJSource", "CrossrefSource", "PubMedSource", "JournalSource",
    "ExamCuratedSource", "extract_jats_license", "is_valid_specialty_case",
    "query_for", "main",
]
