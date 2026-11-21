"""Rights-aware medical source registry.

Extends the existing UCKS source records with the metadata needed to answer one
question safely: *what may HSPTL do with this source?* The registry never
infers permission. A source starts at ``unknown`` and only a named human review
moves it.

Three separate questions are kept apart, because conflating them is the most
common rights error in clinical content systems:

``access``
    Can we read it at all (open, subscription, link-only)?
``reuse``
    May we reproduce text verbatim in a local artefact?
``adaptation``
    May we transform it into derived teaching content?

A source can be openly readable and still forbid adaptation. ``link_only``
sources may be cited by URL and never copied.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

ACCESS_MODES = {"open_access", "subscription", "link_only", "institutional_licence", "unknown"}
REUSE_MODES = {"permitted", "prohibited", "needs_permission", "unknown"}
ADAPTATION_MODES = {"permitted", "prohibited", "needs_permission", "unknown"}

# Ordered catalogue of the source families HSPTL prioritises. `priority` is a
# curation hint for the UI ordering only; it is never treated as evidence
# quality and never unlocks reuse.
PRIORITY_SOURCE_CATALOGUE: tuple[dict[str, Any], ...] = (
    {"key": "nice_guidance", "name": "NICE guidance", "family": "guideline",
     "priority": 1, "default_access": "open_access", "default_reuse": "needs_permission",
     "default_adaptation": "needs_permission",
     "note": "UK national guidance. Summary recommendations may be cited; full text reuse needs permission."},
    {"key": "sign_guidance", "name": "SIGN guidance", "family": "guideline",
     "priority": 1, "default_access": "open_access", "default_reuse": "needs_permission",
     "default_adaptation": "needs_permission",
     "note": "Scottish national guidance. Cite with attribution; do not reproduce wholesale."},
    {"key": "who_guidance", "name": "WHO guidance", "family": "guideline",
     "priority": 2, "default_access": "open_access", "default_reuse": "needs_permission",
     "default_adaptation": "needs_permission",
     "note": "Often CC BY-NC-SA; non-commercial and share-alike terms usually apply."},
    {"key": "cochrane_reviews", "name": "Cochrane systematic reviews", "family": "systematic_review",
     "priority": 1, "default_access": "subscription", "default_reuse": "prohibited",
     "default_adaptation": "needs_permission",
     "note": "Abstracts are citable. Full text is subscription and must not be stored locally."},
    {"key": "pubmed", "name": "PubMed / MEDLINE", "family": "bibliographic",
     "priority": 2, "default_access": "open_access", "default_reuse": "permitted",
     "default_adaptation": "prohibited",
     "note": "Metadata and abstracts are reusable as bibliographic records; the articles are not."},
    {"key": "europe_pmc", "name": "Europe PMC", "family": "bibliographic",
     "priority": 2, "default_access": "open_access", "default_reuse": "permitted",
     "default_adaptation": "needs_permission",
     "note": "Metadata reusable. Full-text reuse depends on each article's licence."},
    {"key": "crossref", "name": "Crossref", "family": "bibliographic",
     "priority": 3, "default_access": "open_access", "default_reuse": "permitted",
     "default_adaptation": "prohibited",
     "note": "Metadata only. Provides DOI resolution, not article text."},
    {"key": "clinicaltrials_gov", "name": "ClinicalTrials.gov", "family": "trial_registry",
     "priority": 3, "default_access": "open_access", "default_reuse": "permitted",
     "default_adaptation": "permitted",
     "note": "US Government work; generally reusable with attribution."},
    {"key": "open_access_journals", "name": "Open-access journals (CC BY family)", "family": "journal",
     "priority": 2, "default_access": "open_access", "default_reuse": "permitted",
     "default_adaptation": "permitted",
     "note": "Only when the specific article licence is CC BY / CC BY-SA. Verify per article."},
    {"key": "nice_bnf", "name": "BNF / BNFc", "family": "formulary",
     "priority": 1, "default_access": "institutional_licence", "default_reuse": "prohibited",
     "default_adaptation": "prohibited",
     "note": "Licensed formulary. Dosing must be verified against the licensed copy, never copied locally."},
    {"key": "snomed_ct", "name": "SNOMED CT", "family": "terminology",
     "priority": 1, "default_access": "institutional_licence", "default_reuse": "needs_permission",
     "default_adaptation": "needs_permission",
     "note": "Affiliate licence required. Concepts may be referenced by identifier."},
    {"key": "institutional_protocols", "name": "Local institutional protocols", "family": "protocol",
     "priority": 1, "default_access": "institutional_licence", "default_reuse": "needs_permission",
     "default_adaptation": "needs_permission",
     "note": "Governed by the institution; reuse requires the owning committee's approval."},
    {"key": "patient_education", "name": "Patient education material", "family": "patient_information",
     "priority": 3, "default_access": "unknown", "default_reuse": "needs_permission",
     "default_adaptation": "needs_permission",
     "note": "Frequently charity-owned. Attribution is not permission to adapt."},
    {"key": "textbooks", "name": "Textbooks and reference works", "family": "book",
     "priority": 3, "default_access": "subscription", "default_reuse": "prohibited",
     "default_adaptation": "prohibited",
     "note": "Cite chapter and page. Never store the text or paraphrase it as teaching content."},
)


# Add content-enriching metadata to the original priority list as well. These
# URLs are discovery starting points; each individual publication still needs
# version, jurisdiction and rights checks before local reproduction or use.
_BASE_SOURCE_DETAILS: dict[str, dict[str, Any]] = {
    "nice_guidance": {"url":"https://www.nice.org.uk/guidance", "content_value":"Evidence-based clinical and public-health recommendations, technology appraisals, quality standards and implementation resources.", "coverage":["multispecialty","primary care","public health","quality improvement"], "integration":"curated_link_out"},
    "sign_guidance": {"url":"https://www.sign.ac.uk/our-guidelines/", "content_value":"Scottish evidence-based clinical guidelines, methodology resources and implementation support.", "coverage":["multispecialty","primary care","specialty practice"], "integration":"curated_link_out"},
    "who_guidance": {"url":"https://www.who.int/publications", "content_value":"International clinical and public-health guidance, technical reports, health systems recommendations and global health resources.", "coverage":["global health","infectious diseases","maternal child health","public health"], "integration":"curated_link_out"},
    "cochrane_reviews": {"url":"https://www.cochranelibrary.com/", "content_value":"Systematic reviews and evidence syntheses for intervention effects, diagnostic questions and healthcare decision-making.", "coverage":["evidence appraisal","systematic review","multispecialty"], "integration":"subscription_or_abstract_metadata"},
    "pubmed": {"url":"https://pubmed.ncbi.nlm.nih.gov/", "content_value":"Biomedical literature discovery, bibliographic metadata, abstracts, MeSH indexing and publication trails.", "coverage":["biomedical research","clinical case reports","guidelines","systematic reviews"], "integration":"managed_metadata_api"},
    "europe_pmc": {"url":"https://europepmc.org/", "content_value":"Life-sciences literature, abstracts, open-access full-text discovery, grants and research data links.", "coverage":["biomedical research","open access","clinical trials","molecular medicine"], "integration":"managed_metadata_api"},
    "crossref": {"url":"https://www.crossref.org/", "content_value":"DOI metadata, citation linking, publication dates, author and journal identifiers for source reconciliation.", "coverage":["bibliography","citation integrity","research discovery"], "integration":"managed_metadata_api"},
    "clinicaltrials_gov": {"url":"https://clinicaltrials.gov/", "content_value":"Registered study protocols, recruitment status, eligibility criteria, outcomes and trial results metadata.", "coverage":["clinical trials","research methods","therapeutics"], "integration":"managed_metadata_api"},
    "open_access_journals": {"url":"https://doaj.org/", "content_value":"Directory for discovering open-access journals; verify each article's specific licence and publication record.", "coverage":["open access","journal discovery","research literacy"], "integration":"article_level_licence_review"},
    "nice_bnf": {"url":"https://bnf.nice.org.uk/", "content_value":"Licensed medicine monographs, interactions, cautions, formulations and prescribing reference information.", "coverage":["prescribing","medicines safety","formulary"], "integration":"institutional_subscription_link"},
    "snomed_ct": {"url":"https://www.snomed.org/", "content_value":"Clinical terminology concepts, hierarchies and relationships for structured clinical meaning and interoperability.", "coverage":["clinical terminology","coding","interoperability"], "integration":"licensed_download_or_api"},
    "institutional_protocols": {"content_value":"Local pathways, escalation procedures and operational standards that reflect institution-specific governance and resources.", "coverage":["local care pathways","service operations","jurisdiction-specific practice"], "integration":"institutional_or_manual_import"},
    "patient_education": {"url":"https://www.nhs.uk/conditions/", "content_value":"Accessible patient-facing explanations, self-care information and safety-netting resources for supported shared learning.", "coverage":["health literacy","patient communication","self-management"], "integration":"curated_link_out"},
    "textbooks": {"content_value":"Structured foundational knowledge, reference chapters and explanatory diagrams across core clinical disciplines.", "coverage":["foundational science","clinical reference","multispecialty"], "integration":"citation_only_or_licensed_link"},
}
for _entry in PRIORITY_SOURCE_CATALOGUE:
    _entry.update(_BASE_SOURCE_DETAILS.get(_entry["key"], {}))

# Extended source directory: records are curated discovery endpoints, not a
# claim that HSPTL can automatically ingest every source. Only the four
# managed metadata connectors have built-in scheduled adapters. All default
# reuse/adaptation permissions below remain conservative and non-authorising.
_EXTENDED_SOURCE_CATALOGUE: tuple[dict[str, Any], ...] = (
    {"key":"cdc_guidance","name":"US Centers for Disease Control and Prevention (CDC)","family":"public_health_guidance","priority":1,"default_access":"open_access","default_reuse":"needs_permission","default_adaptation":"needs_permission","url":"https://www.cdc.gov/","content_value":"Public-health recommendations, surveillance, infection prevention, vaccination and disease-specific clinical resources.","coverage":["infectious diseases","vaccination","public health","travel medicine"],"integration":"curated_link_out","note":"Use the exact page's terms and date; page-level reuse and third-party content require review."},
    {"key":"ecdc_guidance","name":"European Centre for Disease Prevention and Control (ECDC)","family":"public_health_guidance","priority":1,"default_access":"open_access","default_reuse":"needs_permission","default_adaptation":"needs_permission","url":"https://www.ecdc.europa.eu/en","content_value":"European infectious-disease surveillance, threat assessments, technical guidance and public-health reports.","coverage":["infectious diseases","surveillance","antimicrobial resistance","vaccination"],"integration":"curated_link_out","note":"Reports and surveillance data may have distinct reuse and attribution terms; verify each item."},
    {"key":"ukhsa_guidance","name":"UK Health Security Agency (UKHSA)","family":"public_health_guidance","priority":1,"default_access":"open_access","default_reuse":"needs_permission","default_adaptation":"needs_permission","url":"https://www.gov.uk/government/organisations/uk-health-security-agency","content_value":"UK public-health guidance, infectious disease surveillance, outbreak reports and health protection advice.","coverage":["infection control","infectious diseases","outbreak response"],"integration":"curated_link_out","note":"Check Crown copyright, Open Government Licence statements and embedded third-party material per publication."},
    {"key":"egypt_mohp","name":"Egyptian Ministry of Health and Population","family":"national_guideline","priority":1,"default_access":"unknown","default_reuse":"unknown","default_adaptation":"unknown","url":"https://www.mohp.gov.eg/","content_value":"National Egyptian health policy, clinical programmes, public-health campaigns and local context for practice.","coverage":["Egypt","primary care","public health","communicable disease"],"integration":"institutional_or_manual_import","note":"High local relevance; publication availability, currency and reuse permission must be checked for every document."},
    {"key":"gina_strategy","name":"Global Initiative for Asthma (GINA)","family":"specialty_guideline","priority":1,"default_access":"open_access","default_reuse":"needs_permission","default_adaptation":"needs_permission","url":"https://ginasthma.org/","content_value":"Global asthma strategy reports, evidence summaries and implementation resources.","coverage":["respiratory medicine","asthma","paediatrics"],"integration":"curated_link_out","note":"Strategy reports are periodically revised; confirm the version and licence of each file."},
    {"key":"gold_report","name":"Global Initiative for Chronic Obstructive Lung Disease (GOLD)","family":"specialty_guideline","priority":1,"default_access":"open_access","default_reuse":"needs_permission","default_adaptation":"needs_permission","url":"https://goldcopd.org/","content_value":"COPD strategy reports, assessment framework, exacerbation and prevention resources.","coverage":["respiratory medicine","COPD","primary care"],"integration":"curated_link_out","note":"Use the current report version and follow report-specific reproduction and adaptation terms."},
    {"key":"kdigo_guidelines","name":"Kidney Disease: Improving Global Outcomes (KDIGO)","family":"specialty_guideline","priority":1,"default_access":"open_access","default_reuse":"needs_permission","default_adaptation":"needs_permission","url":"https://kdigo.org/guidelines/","content_value":"International kidney-disease clinical practice guidelines, consensus reports and implementation tools.","coverage":["nephrology","AKI","CKD","transplantation"],"integration":"curated_link_out","note":"Guideline PDFs can include separate copyright and adaptation conditions; verify per publication."},
    {"key":"esc_guidelines","name":"European Society of Cardiology (ESC) Guidelines","family":"specialty_guideline","priority":1,"default_access":"open_access","default_reuse":"needs_permission","default_adaptation":"needs_permission","url":"https://www.escardio.org/Guidelines","content_value":"Cardiovascular guidelines, focused updates, clinical practice tools and educational resources.","coverage":["cardiology","heart failure","arrhythmia","acute coronary syndromes"],"integration":"curated_link_out","note":"Citation is not permission to reproduce figures, tables or guideline text."},
    {"key":"aha_guidelines","name":"American Heart Association (AHA) Guidelines","family":"specialty_guideline","priority":1,"default_access":"open_access","default_reuse":"needs_permission","default_adaptation":"needs_permission","url":"https://professional.heart.org/en/guidelines-and-statements","content_value":"Cardiovascular and resuscitation guideline statements, scientific updates and practice resources.","coverage":["cardiology","stroke","resuscitation"],"integration":"curated_link_out","note":"Guideline access does not grant copying or adaptation rights; check statement-specific terms."},
    {"key":"ers_guidelines","name":"European Respiratory Society (ERS)","family":"specialty_guideline","priority":2,"default_access":"open_access","default_reuse":"needs_permission","default_adaptation":"needs_permission","url":"https://www.ersnet.org/guidelines/","content_value":"Respiratory clinical guidelines, technical standards, task-force reports and educational material.","coverage":["respiratory medicine","sleep medicine","critical care"],"integration":"curated_link_out","note":"Individual publications can have publisher-controlled rights and different licences."},
    {"key":"idsa_guidelines","name":"Infectious Diseases Society of America (IDSA)","family":"specialty_guideline","priority":2,"default_access":"open_access","default_reuse":"needs_permission","default_adaptation":"needs_permission","url":"https://www.idsociety.org/practice-guideline/","content_value":"Evidence-based infectious-disease guidelines, antimicrobial guidance and practice statements.","coverage":["infectious diseases","antimicrobial stewardship","HIV"],"integration":"curated_link_out","note":"Check guideline version, update status and rights with the publisher."},
    {"key":"ada_standards","name":"American Diabetes Association (ADA) Standards of Care","family":"specialty_guideline","priority":1,"default_access":"open_access","default_reuse":"needs_permission","default_adaptation":"needs_permission","url":"https://diabetesjournals.org/care/issue","content_value":"Annual evidence-based diabetes standards, screening, diagnosis, risk management and treatment guidance.","coverage":["endocrinology","diabetes","cardiology","renal medicine"],"integration":"curated_link_out","note":"Annual updates make edition tracking essential; article and figure reuse permissions are separate."},
    {"key":"rcog_guidelines","name":"Royal College of Obstetricians and Gynaecologists (RCOG)","family":"specialty_guideline","priority":1,"default_access":"open_access","default_reuse":"needs_permission","default_adaptation":"needs_permission","url":"https://www.rcog.org.uk/guidance/","content_value":"Green-top guidelines, scientific impact papers, patient safety and maternal-care resources.","coverage":["obstetrics","gynaecology","maternal emergencies"],"integration":"curated_link_out","note":"Confirm current status and publication-specific licence before using in a derived artefact."},
    {"key":"figo_guidance","name":"International Federation of Gynecology and Obstetrics (FIGO)","family":"specialty_guideline","priority":2,"default_access":"open_access","default_reuse":"needs_permission","default_adaptation":"needs_permission","url":"https://www.figo.org/","content_value":"International obstetric and gynaecological position statements, recommendations and global health initiatives.","coverage":["obstetrics","gynaecology","reproductive health"],"integration":"curated_link_out","note":"Check publication-level terms and whether material is co-published by a journal."},
    {"key":"rcpch_guidance","name":"Royal College of Paediatrics and Child Health (RCPCH)","family":"specialty_guideline","priority":1,"default_access":"open_access","default_reuse":"needs_permission","default_adaptation":"needs_permission","url":"https://www.rcpch.ac.uk/resources","content_value":"Paediatric clinical resources, standards, audit tools, safeguarding and child-health evidence.","coverage":["paediatrics","neonatology","child health"],"integration":"curated_link_out","note":"Some resources are open for viewing but have restricted reproduction rights."},
    {"key":"aap_guidelines","name":"American Academy of Pediatrics (AAP)","family":"specialty_guideline","priority":2,"default_access":"open_access","default_reuse":"needs_permission","default_adaptation":"needs_permission","url":"https://www.aap.org/","content_value":"Paediatric policy statements, clinical reports, preventive care and child-health education.","coverage":["paediatrics","neonatology","adolescent health"],"integration":"curated_link_out","note":"Some content is member/subscription restricted; verify access and reuse at item level."},
    {"key":"rcs_england","name":"Royal College of Surgeons of England","family":"specialty_guideline","priority":2,"default_access":"open_access","default_reuse":"needs_permission","default_adaptation":"needs_permission","url":"https://www.rcseng.ac.uk/standards-and-research/","content_value":"Surgical standards, commissioning guidance, quality improvement and operative-care resources.","coverage":["general surgery","trauma","perioperative care"],"integration":"curated_link_out","note":"Standards and publications may have separate terms; use source links and verify version."},
    {"key":"gin_network","name":"Guidelines International Network (G-I-N)","family":"guideline_index","priority":2,"default_access":"open_access","default_reuse":"needs_permission","default_adaptation":"needs_permission","url":"https://g-i-n.net/","content_value":"Guideline community, guideline library and methods resources for locating national and specialty guidance.","coverage":["multispecialty","guideline methods","health systems"],"integration":"curated_link_out","note":"An index/discovery network; verify the issuing body's source document and licence."},
    {"key":"doaj","name":"Directory of Open Access Journals (DOAJ)","family":"journal_index","priority":2,"default_access":"open_access","default_reuse":"permitted","default_adaptation":"needs_permission","url":"https://doaj.org/","content_value":"Discovery of peer-reviewed open-access journals and article metadata; article licences vary individually.","coverage":["multispecialty","open access research"],"integration":"metadata_search_link_out","note":"Journal inclusion does not make every article CC BY. Confirm the licence on each article page."},
    {"key":"plos","name":"Public Library of Science (PLOS)","family":"open_access_publisher","priority":2,"default_access":"open_access","default_reuse":"permitted","default_adaptation":"permitted","url":"https://plos.org/","content_value":"Open research articles across medicine, public health, biology and global health.","coverage":["multispecialty","public health","translational research"],"integration":"metadata_search_link_out","note":"Check each article's stated licence and any third-party figures or materials."},
    {"key":"bmc_springer_open","name":"BMC / Springer Nature Open Access journals","family":"open_access_publisher","priority":2,"default_access":"open_access","default_reuse":"needs_permission","default_adaptation":"needs_permission","url":"https://www.biomedcentral.com/","content_value":"Clinical and biomedical open-access research, reviews, case reports and methods papers.","coverage":["multispecialty","clinical research","case reports"],"integration":"metadata_search_link_out","note":"Mixed licences across journals and articles; verify the exact article licence before any reuse."},
    {"key":"medrxiv","name":"medRxiv preprint server","family":"preprint_repository","priority":3,"default_access":"open_access","default_reuse":"needs_permission","default_adaptation":"prohibited","url":"https://www.medrxiv.org/","content_value":"Recent clinical and health-science preprints useful for research awareness and evidence-gap tracking.","coverage":["multispecialty","emerging evidence"],"integration":"metadata_search_link_out","note":"Preprints are not peer reviewed. Label clearly and never treat as equivalent to validated guidance."},
    {"key":"openalex","name":"OpenAlex scholarly metadata","family":"bibliographic","priority":3,"default_access":"open_access","default_reuse":"permitted","default_adaptation":"prohibited","url":"https://openalex.org/","content_value":"Open scholarly metadata for works, authors, institutions, concepts and citation-network discovery.","coverage":["multispecialty","research mapping"],"integration":"metadata_api_available","note":"Metadata discovery only; it does not supply reuse rights for linked full-text articles."},
    {"key":"who_ictrp","name":"WHO International Clinical Trials Registry Platform (ICTRP)","family":"trial_registry","priority":2,"default_access":"open_access","default_reuse":"needs_permission","default_adaptation":"needs_permission","url":"https://trialsearch.who.int/","content_value":"Global trial-registry search and discovery of prospective/ongoing studies across primary registries.","coverage":["clinical trials","evidence gaps","multispecialty"],"integration":"curated_search_link_out","note":"Registry access and bulk download/API conditions differ; use official access mechanisms."},
    {"key":"isrctn_registry","name":"ISRCTN Clinical Study Registry","family":"trial_registry","priority":3,"default_access":"open_access","default_reuse":"needs_permission","default_adaptation":"needs_permission","url":"https://www.isrctn.com/","content_value":"Registered clinical studies, study status, protocol summaries and linked publications.","coverage":["clinical trials","multispecialty"],"integration":"curated_search_link_out","note":"Registry summaries are citable; verify terms before extraction or redistribution."},
    {"key":"eu_ctis","name":"EU Clinical Trials Information System (CTIS)","family":"trial_registry","priority":3,"default_access":"open_access","default_reuse":"needs_permission","default_adaptation":"needs_permission","url":"https://euclinicaltrials.eu/","content_value":"European Union clinical trial search, status and public trial information.","coverage":["clinical trials","medicines regulation"],"integration":"curated_search_link_out","note":"Public portal terms and trial-document disclosure rules apply; do not infer rights from visibility."},
    {"key":"who_gho","name":"WHO Data / Global Health Observatory","family":"health_statistics","priority":1,"default_access":"open_access","default_reuse":"needs_permission","default_adaptation":"needs_permission","url":"https://data.who.int/","content_value":"Country-comparable health indicators, mortality, disease burden, health systems and inequality data.","coverage":["global health","epidemiology","public health"],"integration":"data_api_or_download","note":"Check indicator metadata, methods, update date and dataset-specific reuse terms."},
    {"key":"oecd_health_stats","name":"OECD Health Statistics","family":"health_statistics","priority":3,"default_access":"open_access","default_reuse":"needs_permission","default_adaptation":"needs_permission","url":"https://www.oecd.org/en/data/datasets/oecd-health-statistics.html","content_value":"Comparative health-system, expenditure, workforce, outcomes and service indicators.","coverage":["health systems","health economics","public health"],"integration":"data_download_link_out","note":"Check OECD data licensing and citation conditions for the selected table or dataset."},
    {"key":"world_bank_health","name":"World Bank Health, Nutrition and Population Data","family":"health_statistics","priority":3,"default_access":"open_access","default_reuse":"needs_permission","default_adaptation":"needs_permission","url":"https://data.worldbank.org/topic/health","content_value":"Country and regional indicators for health financing, outcomes, population and development.","coverage":["global health","health economics","epidemiology"],"integration":"data_api_or_download","note":"Dataset/source licences can vary; retain indicator definitions and retrieval date."},
    {"key":"cdc_data","name":"CDC Open Data","family":"health_statistics","priority":3,"default_access":"open_access","default_reuse":"needs_permission","default_adaptation":"needs_permission","url":"https://data.cdc.gov/","content_value":"US public-health datasets, surveillance extracts and downloadable indicator collections.","coverage":["epidemiology","public health","surveillance"],"integration":"data_api_or_download","note":"Review dataset notes, privacy limits and third-party restrictions before local import."},
    {"key":"ihme_ghdx","name":"IHME Global Health Data Exchange (GHDx)","family":"health_statistics","priority":3,"default_access":"open_access","default_reuse":"needs_permission","default_adaptation":"needs_permission","url":"https://ghdx.healthdata.org/","content_value":"Global burden of disease studies, survey catalogues and population-health datasets.","coverage":["global burden of disease","epidemiology","public health"],"integration":"data_download_link_out","note":"Licences and access conditions are dataset-specific; review methods and uncertainty intervals."},
    {"key":"dailymed","name":"DailyMed","family":"medicines_reference","priority":1,"default_access":"open_access","default_reuse":"needs_permission","default_adaptation":"needs_permission","url":"https://dailymed.nlm.nih.gov/dailymed/","content_value":"US FDA-submitted prescribing information and structured drug labelling.","coverage":["clinical pharmacology","medicines safety","prescribing"],"integration":"metadata_api_available","note":"Regulatory labels are jurisdiction-specific and not a substitute for local formulary guidance."},
    {"key":"fda_drug_labels","name":"US Food and Drug Administration (FDA) drug safety and labels","family":"medicines_regulator","priority":2,"default_access":"open_access","default_reuse":"needs_permission","default_adaptation":"needs_permission","url":"https://www.fda.gov/drugs","content_value":"Drug approvals, safety communications, labelling and regulatory notices.","coverage":["clinical pharmacology","medicines safety","regulatory science"],"integration":"curated_link_out","note":"Check official source, label date and applicability outside the United States."},
    {"key":"ema_medicines","name":"European Medicines Agency (EMA)","family":"medicines_regulator","priority":2,"default_access":"open_access","default_reuse":"needs_permission","default_adaptation":"needs_permission","url":"https://www.ema.europa.eu/en/medicines","content_value":"European public assessment reports, product information, safety referrals and medicine updates.","coverage":["clinical pharmacology","medicines safety","regulatory science"],"integration":"curated_link_out","note":"Regulatory decisions and labels are EU-specific; assess local product authorisation and terms."},
    {"key":"lactmed","name":"LactMed","family":"medicines_reference","priority":2,"default_access":"open_access","default_reuse":"needs_permission","default_adaptation":"needs_permission","url":"https://www.ncbi.nlm.nih.gov/books/NBK501922/","content_value":"Evidence summaries on drugs and chemicals during breastfeeding with cited primary literature.","coverage":["obstetrics","paediatrics","clinical pharmacology"],"integration":"curated_link_out","note":"Use the latest monograph and individual clinical context; retain source attribution and verify reuse."},
    {"key":"icd11_who","name":"WHO ICD-11","family":"clinical_classification","priority":2,"default_access":"open_access","default_reuse":"needs_permission","default_adaptation":"needs_permission","url":"https://icd.who.int/","content_value":"International disease classification, coding reference and terminology browser.","coverage":["coding","epidemiology","multispecialty"],"integration":"api_or_browser","note":"Use official release/version and comply with WHO licensing and implementation terms."},
    {"key":"loinc","name":"LOINC","family":"clinical_terminology","priority":2,"default_access":"open_access","default_reuse":"needs_permission","default_adaptation":"needs_permission","url":"https://loinc.org/","content_value":"Standard identifiers for laboratory tests, clinical observations, documents and panels.","coverage":["laboratory medicine","interoperability","clinical data"],"integration":"licensed_download_or_api","note":"Review LOINC terms of use and distribution rules before importing or redistributing files."},
    {"key":"rxnorm","name":"RxNorm","family":"medicines_terminology","priority":2,"default_access":"open_access","default_reuse":"needs_permission","default_adaptation":"needs_permission","url":"https://www.nlm.nih.gov/research/umls/rxnorm/","content_value":"Normalised clinical drug names and relationships for medication data interoperability.","coverage":["medicines","prescribing","interoperability"],"integration":"download_or_api","note":"Verify current UMLS/RxNorm access and licensing conditions for your country and use."},
    {"key":"orphanet","name":"Orphanet","family":"rare_disease_reference","priority":3,"default_access":"open_access","default_reuse":"needs_permission","default_adaptation":"needs_permission","url":"https://www.orpha.net/","content_value":"Rare disease nomenclature, disease summaries, prevalence and expert-centre information.","coverage":["medical genetics","rare disease","paediatrics"],"integration":"curated_link_out","note":"Dataset and nomenclature distribution have specific terms; verify licence and edition."},
    {"key":"radiopaedia","name":"Radiopaedia","family":"clinical_imaging_reference","priority":2,"default_access":"open_access","default_reuse":"needs_permission","default_adaptation":"prohibited","url":"https://radiopaedia.org/","content_value":"Radiology cases, imaging findings and modality-based teaching explanations.","coverage":["radiology","emergency medicine","all specialties"],"integration":"curated_link_out","note":"Images and case pages are rights-sensitive; link out and do not copy/adapt without express permission."},
    {"key":"wikimedia_commons","name":"Wikimedia Commons medical media","family":"medical_media","priority":3,"default_access":"open_access","default_reuse":"needs_permission","default_adaptation":"needs_permission","url":"https://commons.wikimedia.org/","content_value":"Potentially reusable medical diagrams and images with file-level licence and attribution metadata.","coverage":["medical education","anatomy","radiology"],"integration":"file_level_licence_review","note":"Every file requires an individual licence, author, attribution and derivative-use check."},
    {"key":"merck_manual","name":"Merck Manual Professional Edition","family":"clinical_reference","priority":3,"default_access":"open_access","default_reuse":"needs_permission","default_adaptation":"prohibited","url":"https://www.merckmanuals.com/professional","content_value":"Clinically oriented reference summaries across medicine, surgery, paediatrics and special populations.","coverage":["multispecialty","diagnosis","clinical reference"],"integration":"curated_link_out","note":"Reading access does not authorise local copying or adaptation; keep as link-out reference."},
    {"key":"bmj_best_practice","name":"BMJ Best Practice","family":"clinical_reference","priority":2,"default_access":"subscription","default_reuse":"prohibited","default_adaptation":"prohibited","url":"https://bestpractice.bmj.com/","content_value":"Point-of-care clinical topic summaries, differential diagnosis and evidence-based practice information.","coverage":["multispecialty","point-of-care learning"],"integration":"institutional_subscription_link","note":"Subscription resource. Do not scrape, locally store or adapt its content."},
)

PRIORITY_SOURCE_CATALOGUE = PRIORITY_SOURCE_CATALOGUE + _EXTENDED_SOURCE_CATALOGUE


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _id() -> str:
    return "src_" + uuid.uuid4().hex


class RightsError(ValueError):
    """Raised when a rights-dependent action is attempted without a basis."""


@dataclass(slots=True)
class SourceRights:
    """The rights envelope for one registered source."""

    access: str = "unknown"
    reuse: str = "unknown"
    adaptation: str = "unknown"
    licence: str = ""
    licence_uri: str = ""
    attribution: str = ""
    jurisdiction: str = "global"
    reviewer: str = ""
    rationale: str = ""
    evidence_reference: str = ""
    reviewed_at: str = ""

    def __post_init__(self) -> None:
        for name, allowed in (("access", ACCESS_MODES), ("reuse", REUSE_MODES),
                              ("adaptation", ADAPTATION_MODES)):
            value = getattr(self, name)
            if value not in allowed:
                raise RightsError(f"Unsupported {name} value: {value!r}")

    @property
    def is_reviewed(self) -> bool:
        return bool(self.reviewer and self.reviewed_at)

    def allows_copy(self) -> bool:
        """May the source text be reproduced verbatim in a local artefact?"""
        return self.access != "link_only" and self.reuse == "permitted"

    def allows_adaptation(self) -> bool:
        """May the source be transformed into derived teaching content?"""
        if self.access == "link_only":
            return False
        return self.reuse == "permitted" and self.adaptation == "permitted"

    def allows_citation(self) -> bool:
        """Citation by reference is always allowed; only the text is restricted."""
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "access": self.access, "reuse": self.reuse, "adaptation": self.adaptation,
            "licence": self.licence, "licence_uri": self.licence_uri,
            "attribution": self.attribution, "jurisdiction": self.jurisdiction,
            "reviewer": self.reviewer, "rationale": self.rationale,
            "evidence_reference": self.evidence_reference, "reviewed_at": self.reviewed_at,
            "is_reviewed": self.is_reviewed,
            "capabilities": {
                "cite": self.allows_citation(),
                "copy_verbatim": self.allows_copy(),
                "adapt": self.allows_adaptation(),
            },
        }


class SourceRegistry:
    """Durable registry of sources, their rights envelope and their priority.

    Sits alongside ``ucks_sources`` rather than replacing it: the UCKS table
    remains the identity and ingestion anchor, and this table holds the
    rights-aware curation layer keyed by the same ``source_id``.
    """

    def __init__(self, store):
        self.store = store
        self._initialise()

    def _initialise(self) -> None:
        with self.store.transaction() as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS source_registry (
                source_id TEXT PRIMARY KEY,
                catalogue_key TEXT NOT NULL DEFAULT '',
                family TEXT NOT NULL DEFAULT 'other',
                priority INTEGER NOT NULL DEFAULT 50,
                access TEXT NOT NULL DEFAULT 'unknown',
                reuse TEXT NOT NULL DEFAULT 'unknown',
                adaptation TEXT NOT NULL DEFAULT 'unknown',
                licence TEXT NOT NULL DEFAULT '',
                licence_uri TEXT NOT NULL DEFAULT '',
                attribution TEXT NOT NULL DEFAULT '',
                jurisdiction TEXT NOT NULL DEFAULT 'global',
                reviewer TEXT NOT NULL DEFAULT '',
                rationale TEXT NOT NULL DEFAULT '',
                evidence_reference TEXT NOT NULL DEFAULT '',
                reviewed_at TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_registry_priority ON source_registry(priority, family);
            CREATE INDEX IF NOT EXISTS idx_registry_rights ON source_registry(reuse, adaptation);
            CREATE TABLE IF NOT EXISTS source_registry_history (
                id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                action TEXT NOT NULL,
                snapshot_json TEXT NOT NULL DEFAULT '{}',
                reviewer TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_registry_history_source
                ON source_registry_history(source_id, created_at DESC);
            """)
            conn.execute(
                "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES(31, ?)", (_now(),)
            )

    # -- catalogue -------------------------------------------------------- #

    @staticmethod
    def catalogue() -> list[dict[str, Any]]:
        return [dict(entry) for entry in sorted(PRIORITY_SOURCE_CATALOGUE, key=lambda e: (e["priority"], e["key"]))]

    @staticmethod
    def catalogue_entry(key: str) -> dict[str, Any] | None:
        for entry in PRIORITY_SOURCE_CATALOGUE:
            if entry["key"] == key:
                return dict(entry)
        return None

    # -- registration ----------------------------------------------------- #

    def register(self, *, source_id: str, catalogue_key: str = "", family: str = "",
                 priority: int | None = None, rights: SourceRights | None = None) -> dict[str, Any]:
        """Register or refresh the curation record for an existing UCKS source.

        When a catalogue key is supplied the catalogue defaults seed the record,
        but they seed *permission-neutral* values only: the catalogue records what
        is typical for that family, and the record still reports ``unknown``
        until a reviewer confirms it.
        """
        entry = self.catalogue_entry(catalogue_key) if catalogue_key else None
        if catalogue_key and entry is None:
            raise RightsError(f"Unknown catalogue key: {catalogue_key!r}")
        rights = rights or SourceRights()
        now = _now()
        resolved_family = family or (entry["family"] if entry else "other")
        resolved_priority = priority if priority is not None else (entry["priority"] if entry else 50)
        resolved_priority = max(1, min(int(resolved_priority), 99))
        with self.store.transaction() as conn:
            existing = conn.execute("SELECT source_id FROM source_registry WHERE source_id=?",
                                    (source_id,)).fetchone()
            if existing:
                conn.execute(
                    """UPDATE source_registry SET catalogue_key=?, family=?, priority=?,
                       updated_at=? WHERE source_id=?""",
                    (catalogue_key, resolved_family, resolved_priority, now, source_id),
                )
            else:
                conn.execute(
                    """INSERT INTO source_registry
                       (source_id,catalogue_key,family,priority,access,reuse,adaptation,licence,
                        licence_uri,attribution,jurisdiction,reviewer,rationale,evidence_reference,
                        reviewed_at,created_at,updated_at)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (source_id, catalogue_key, resolved_family, resolved_priority,
                     rights.access, rights.reuse, rights.adaptation, rights.licence,
                     rights.licence_uri, rights.attribution, rights.jurisdiction,
                     rights.reviewer, rights.rationale, rights.evidence_reference,
                     rights.reviewed_at, now, now),
                )
            self._history(conn, source_id, "registered", {"catalogue_key": catalogue_key}, rights.reviewer)
        return self.get(source_id)  # type: ignore[return-value]

    def record_rights(self, source_id: str, rights: SourceRights) -> dict[str, Any]:
        """Record a human rights decision. A named reviewer is mandatory."""
        if not rights.reviewer.strip():
            raise RightsError("A named reviewer is required to record source rights")
        if not rights.rationale.strip():
            raise RightsError("A rationale is required to record source rights")
        if rights.reuse == "permitted" and not rights.licence.strip():
            raise RightsError("Permitted reuse requires the licence to be recorded")
        stamped = SourceRights(
            access=rights.access, reuse=rights.reuse, adaptation=rights.adaptation,
            licence=rights.licence, licence_uri=rights.licence_uri,
            attribution=rights.attribution, jurisdiction=rights.jurisdiction,
            reviewer=rights.reviewer, rationale=rights.rationale,
            evidence_reference=rights.evidence_reference, reviewed_at=_now(),
        )
        now = _now()
        with self.store.transaction() as conn:
            if conn.execute("SELECT 1 FROM source_registry WHERE source_id=?", (source_id,)).fetchone() is None:
                raise RightsError("Register the source before recording its rights")
            conn.execute(
                """UPDATE source_registry SET access=?,reuse=?,adaptation=?,licence=?,licence_uri=?,
                   attribution=?,jurisdiction=?,reviewer=?,rationale=?,evidence_reference=?,
                   reviewed_at=?,updated_at=? WHERE source_id=?""",
                (stamped.access, stamped.reuse, stamped.adaptation, stamped.licence,
                 stamped.licence_uri, stamped.attribution, stamped.jurisdiction,
                 stamped.reviewer, stamped.rationale, stamped.evidence_reference,
                 stamped.reviewed_at, now, source_id),
            )
            self._history(conn, source_id, "rights_recorded", stamped.to_dict(), stamped.reviewer)
        return self.get(source_id)  # type: ignore[return-value]

    def _history(self, conn, source_id: str, action: str, snapshot: dict[str, Any], reviewer: str) -> None:
        conn.execute(
            "INSERT INTO source_registry_history(id,source_id,action,snapshot_json,reviewer,created_at)"
            " VALUES(?,?,?,?,?,?)",
            ("srch_" + uuid.uuid4().hex, source_id, action,
             json.dumps(snapshot, ensure_ascii=False), reviewer[:160], _now()),
        )

    # -- reads ------------------------------------------------------------ #

    def get(self, source_id: str) -> dict[str, Any] | None:
        with self.store.transaction() as conn:
            row = conn.execute("SELECT * FROM source_registry WHERE source_id=?", (source_id,)).fetchone()
        if row is None:
            return None
        record = dict(row)
        rights = SourceRights(
            access=record["access"], reuse=record["reuse"], adaptation=record["adaptation"],
            licence=record["licence"], licence_uri=record["licence_uri"],
            attribution=record["attribution"], jurisdiction=record["jurisdiction"],
            reviewer=record["reviewer"], rationale=record["rationale"],
            evidence_reference=record["evidence_reference"], reviewed_at=record["reviewed_at"],
        )
        record["rights"] = rights.to_dict()
        record["catalogue_entry"] = self.catalogue_entry(record["catalogue_key"]) if record["catalogue_key"] else None
        return record

    def rights_for(self, source_id: str) -> SourceRights:
        """Return the rights envelope, defaulting to fully restrictive.

        An unregistered source is treated as ``unknown`` on every axis, which
        means it can be cited but not copied or adapted.
        """
        record = self.get(source_id)
        if record is None:
            return SourceRights()
        return SourceRights(
            access=record["access"], reuse=record["reuse"], adaptation=record["adaptation"],
            licence=record["licence"], licence_uri=record["licence_uri"],
            attribution=record["attribution"], jurisdiction=record["jurisdiction"],
            reviewer=record["reviewer"], rationale=record["rationale"],
            evidence_reference=record["evidence_reference"], reviewed_at=record["reviewed_at"],
        )

    def list_sources(self, *, family: str = "", only_reviewed: bool = False) -> list[dict[str, Any]]:
        sql = "SELECT source_id FROM source_registry WHERE 1=1"
        params: list[Any] = []
        if family:
            sql += " AND family=?"
            params.append(family)
        if only_reviewed:
            sql += " AND reviewer<>''"
        sql += " ORDER BY priority, source_id"
        with self.store.transaction() as conn:
            ids = [row["source_id"] for row in conn.execute(sql, params)]
        return [item for item in (self.get(sid) for sid in ids) if item]

    def history(self, source_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
        with self.store.transaction() as conn:
            rows = conn.execute(
                "SELECT * FROM source_registry_history WHERE source_id=? ORDER BY created_at DESC LIMIT ?",
                (source_id, max(1, min(int(limit), 500))),
            ).fetchall()
        items = []
        for row in rows:
            item = dict(row)
            item["snapshot"] = json.loads(item.pop("snapshot_json") or "{}")
            items.append(item)
        return items

    # -- enforcement ------------------------------------------------------ #

    def require_copy(self, source_id: str) -> SourceRights:
        rights = self.rights_for(source_id)
        if not rights.allows_copy():
            raise RightsError(
                "This source may not be reproduced verbatim. Record a permitted reuse "
                "decision with a licence before copying its text.")
        return rights

    def require_adaptation(self, source_id: str) -> SourceRights:
        rights = self.rights_for(source_id)
        if not rights.allows_adaptation():
            raise RightsError(
                "This source may not be adapted into derived content. Adaptation requires "
                "permitted reuse and permitted adaptation recorded by a named reviewer.")
        return rights

    def summary(self) -> dict[str, Any]:
        with self.store.transaction() as conn:
            total = conn.execute("SELECT COUNT(*) AS n FROM source_registry").fetchone()["n"]
            reviewed = conn.execute(
                "SELECT COUNT(*) AS n FROM source_registry WHERE reviewer<>''").fetchone()["n"]
            by_reuse = {row["reuse"]: row["n"] for row in conn.execute(
                "SELECT reuse, COUNT(*) AS n FROM source_registry GROUP BY reuse")}
            by_family = {row["family"]: row["n"] for row in conn.execute(
                "SELECT family, COUNT(*) AS n FROM source_registry GROUP BY family")}
        return {
            "registered": int(total),
            "reviewed": int(reviewed),
            "unreviewed": int(total) - int(reviewed),
            "by_reuse": by_reuse,
            "by_family": by_family,
            "catalogue_size": len(PRIORITY_SOURCE_CATALOGUE),
            "note": ("Rights are recorded by named human review. Automated licence screening "
                     "is a prompt to review, never a decision."),
        }
