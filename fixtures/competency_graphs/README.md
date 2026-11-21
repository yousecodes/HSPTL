# Competency reference graph fixtures

Place authorized CaSS JSON-LD or MedBiquitous Competency Framework XML source fixtures here. The importers in `backend/hsptl_core/hsp_tl40/dataset_imports.py` normalize supplied data into `hsptl.reference-graph/1.0` files for tests and mapping review only. They do not create runtime competency assertions, mastery state, learner profiles or clinical facts.

The included CaSS and MedBiquitous inputs are synthetic examples, not copied official frameworks. No third-party competency framework content is bundled in this package. CaSS competency objects and relations are represented as a directed graph; the MedBiquitous v1 competency schema is documented by its publisher as a draft, so source schema revision and mappings must be reviewed before use.
