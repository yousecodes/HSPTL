"""Versioned ontology vocabulary and deterministic DL-safe entailment profile.

Profile: finite, named-class taxonomy with transitive subclass closure and
explicit object-property assertions. This is intentionally not advertised as
full OWL-DL; unsupported constructors must abstain rather than approximate.
"""
ONTOLOGY_VERSION = "1.0.0"
CLASSES = {
    "ClinicalEntity": [], "Condition": ["ClinicalEntity"], "Finding": ["ClinicalEntity"],
    "Intervention": ["ClinicalEntity"], "Investigation": ["ClinicalEntity"],
    "Population": ["ClinicalEntity"], "Outcome": ["ClinicalEntity"],
    "EvidenceEntity": [], "Guideline": ["EvidenceEntity"], "Trial": ["EvidenceEntity"],
    "SystematicReview": ["EvidenceEntity"], "CaseReport": ["EvidenceEntity"],
    "LearningObject": [], "Competency": [], "Appraisal": [], "SourceSpan": [],
    "ClinicalQuestion": [], "Recommendation": ["LearningObject"],
}
RELATIONSHIPS = {
    "supports": ("EvidenceEntity", "ClinicalEntity"),
    "derived_from": ("LearningObject", "EvidenceEntity"),
    "has_appraisal": ("EvidenceEntity", "Appraisal"),
    "has_source_span": ("LearningObject", "SourceSpan"),
    "assesses": ("LearningObject", "Competency"),
    "requires_prerequisite": ("Competency", "Competency"),
    "supersedes": ("EvidenceEntity", "EvidenceEntity"),
    "contradicts": ("EvidenceEntity", "EvidenceEntity"),
    "supports_learning_objective": ("LearningObject", "Competency"),
}
DL_PROFILE = {
    "name": "HSPTL-DL-FiniteTaxonomy-1",
    "supported": ["named classes", "multiple inheritance", "transitive subclass closure", "typed object properties", "explicit assertions"],
    "unsupported_abstain": ["existential restrictions", "cardinality restrictions", "negation", "disjunction", "universal restrictions", "anonymous individuals", "open-world negative entailment"],
    "semantics": "positive, finite named-class entailment; absence is unknown, never false",
}

def validate_class(name: str) -> bool:
    return name in CLASSES

def ancestors(class_name: str) -> set[str]:
    if class_name not in CLASSES:
        raise ValueError(f"Unknown ontology class: {class_name}")
    found: set[str] = set()
    pending = list(CLASSES[class_name])
    while pending:
        parent = pending.pop()
        if parent in found:
            continue
        found.add(parent)
        pending.extend(CLASSES.get(parent, []))
    return found

def entails_type(asserted_type: str, requested_type: str) -> bool:
    return asserted_type == requested_type or requested_type in ancestors(asserted_type)
