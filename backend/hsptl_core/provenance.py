"""Clinical fact provenance contracts shared by importers and learning modules."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any


class FactStatus(StrEnum):
    DOCUMENTED = "documented"
    DERIVED = "derived"
    AUTHORED = "authored"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class ClinicalFact:
    key: str
    value: Any
    status: FactStatus
    source_type: str | None = None
    source_id: str | None = None
    source_path: str | None = None
    observed_at: str | None = None
    derivation: str | None = None
    uncertainty: str | None = None

    def __post_init__(self) -> None:
        if self.status == FactStatus.UNAVAILABLE and self.value not in (None, "", [], {}):
            raise ValueError("Unavailable clinical facts cannot contain a clinical value")
        if self.status == FactStatus.DOCUMENTED and not (self.source_type and self.source_id):
            raise ValueError("Documented facts require a source resource type and resource id")
        if self.status == FactStatus.DERIVED and not self.derivation:
            raise ValueError("Derived facts require an explicit derivation description")

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["status"] = self.status.value
        return result


def unavailable_fact(key: str, reason: str = "Not documented in the available source") -> ClinicalFact:
    return ClinicalFact(key=key, value=None, status=FactStatus.UNAVAILABLE, uncertainty=reason)
