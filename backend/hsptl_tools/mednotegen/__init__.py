"""HSPTL MedNoteGen: deterministic Synthea FHIR note generation."""
__version__ = "1.1.0"
from .service import MedNoteGenService
__all__ = ["MedNoteGenService", "__version__"]
