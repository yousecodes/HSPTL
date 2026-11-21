# SNOMED CT RF2 local import

No SNOMED CT release content is bundled. Obtain the RF2 edition you are entitled to use and provide its **Snapshot** Concept and Description files locally. The importer requires an explicit `licensed_use_confirmed=True` acknowledgement and records release metadata plus source-file SHA-256 hashes in the canonical HSPTL event ledger.

The embedded index performs exact concept-id or exact active description lookup. It does not implement Expression Constraint Language (ECL), reason over relationships, or substitute for a terminology server. Configure the Snowstorm port for full ECL.
