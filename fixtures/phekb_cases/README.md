# PheKB-derived PROforma fixtures

- `phekb_style_case_001.json` and `.proforma.json`: synthetic shape test for curator normalization; not a published phenotype.
- `phekb_type2_diabetes_source.json`: bounded source notes and normalized input vocabulary for the published PheKB Type 2 Diabetes (T2D) algorithm.
- `phekb_type2_diabetes_ehr_plus.proforma.json`: executable PROforma subset re-expression of the preferred EHR+ case path and universal control path.

Source: https://phekb.org/sites/phenotype/files/Type%202%20Diabetes.pdf

The Type 2 Diabetes fixture contains only algorithm logic and synthetic facts. It does not contain patient data, full site-specific ICD/medication code sets, extraction queries, the alternative EHR-only path, or a validated clinical implementation. Unknown input facts remain unknown; they are never defaulted to false. These files are test fixtures, not production clinical infrastructure.
