"""Curated, deliberately conservative educational content for HSPTL."""
from __future__ import annotations

STAGES = [
    {
        "name": "Presentation",
        "goal": "Define the problem and identify immediate threats.",
        "questions": [
            "Write a one-sentence problem representation using documented facts only.",
            "Which three missing history or examination details would most change your assessment, and why?",
            "What time-critical red flags must be actively excluded?",
        ],
        "rubric": [
            "Relevant background and context", "Chronology and symptom characterisation",
            "Relevant positive findings", "Explicit negatives separated from missing data",
            "Focused further history and examination", "Immediate risks prioritised",
        ],
        "quiz": [
            ("A field is absent from the extract. What does this mean?", ["Confirmed normal", "Unknown / not available in this extract", "The test was never performed"], 1, "Missing data are unknown; they are not negative or normal results."),
            ("A good problem representation prioritises:", ["Relevant background, time course and discriminating findings", "Every historic code", "A final diagnosis before assessment"], 0, "The representation compresses information that shapes clinical reasoning."),
            ("When a time-critical red flag is identified:", ["Continue the routine sequence", "Prioritise urgent assessment and escalation", "Wait for routine follow-up"], 1, "Potential immediate threats take precedence over routine case completion."),
        ],
    },
    {
        "name": "Clinical reasoning",
        "goal": "Generate, compare and prioritise explanations.",
        "questions": [
            "Construct a concise problem representation and state your leading diagnosis.",
            "Rank three plausible alternatives, including a dangerous diagnosis not to miss.",
            "For each leading possibility, identify supporting evidence, opposing evidence and the most useful discriminator.",
        ],
        "rubric": [
            "Concise problem representation", "Relevant differential diagnoses",
            "Likelihood-based prioritisation", "Dangerous alternatives considered",
            "Supporting and opposing evidence", "Uncertainty and discriminating features",
        ],
        "quiz": [
            ("A useful differential should be:", ["Ranked with supporting and opposing evidence", "A long unranked list", "Limited to coded diagnoses"], 0, "A differential should reflect probability, evidence and consequence."),
            ("A coded Synthea condition is best treated as:", ["A source-recorded entry requiring context", "Proof every symptom is explained", "A definitive independent diagnosis"], 0, "A coded entry is part of the synthetic record; it is not a complete clinical assessment."),
            ("Clinical prioritisation should consider:", ["Only prevalence", "Only severity", "Likelihood and harm if missed"], 2, "Probability and consequence both matter when prioritising."),
        ],
    },
    {
        "name": "Investigations",
        "goal": "Choose tests that answer a clinical question and interpret results in context.",
        "questions": [
            "Which available result is most relevant to your differential, and why?",
            "What investigation would you choose next, and what decision could it change?",
            "Which data are incomplete, discordant or uninterpretable?",
        ],
        "rubric": [
            "Clinical question stated", "Appropriate first-line investigations",
            "Test choice justified", "Results interpreted with units and context",
            "Limitations and missing data identified", "Next decision linked to results",
        ],
        "quiz": [
            ("A test name is present but its result is blank. The correct interpretation is:", ["Normal", "Abnormal", "Unavailable / uninterpretable from this extract"], 2, "The presence of a test record without a value does not establish a result."),
            ("Investigation choice should primarily be guided by:", ["A focused clinical question and expected decision impact", "Ordering every possible test", "Whatever was ordered in another case"], 0, "Tests should address a clinical question and be interpreted in context."),
            ("A numeric laboratory result should be interpreted with:", ["The number alone", "Units, age, sex where relevant, method and clinical context", "An assumed adult reference range"], 1, "Reference intervals and interpretation depend on population and method."),
        ],
    },
    {
        "name": "Management",
        "goal": "Plan safe, individualised and evidence-informed care.",
        "questions": [
            "Separate management documented in the source record from management you propose.",
            "Describe the immediate priorities, escalation threshold and monitoring plan.",
            "Identify medication, allergy, age, weight, comorbidity and follow-up considerations.",
        ],
        "rubric": [
            "Immediate stabilisation and safety", "Evidence-informed options",
            "Medication safety and contraindications", "Patient-specific factors considered",
            "Escalation and monitoring plan", "Follow-up and safety-netting",
        ],
        "quiz": [
            ("A medication request from several years ago is found. You should:", ["Assume it is current", "Treat it as a historical record until current use is verified", "Automatically renew it"], 1, "A historical request does not prove current use or suitability."),
            ("No allergy record is found. This means:", ["No allergies", "The patient is allergic to all drugs", "No linked record was found; verify allergy status"], 2, "Absence of a record is not evidence that no allergy exists."),
            ("A management plan should include:", ["Only a drug name", "Safety, monitoring, escalation and follow-up", "Only the diagnosis"], 1, "A safe plan includes assessment, monitoring, escalation and review."),
        ],
    },
    {
        "name": "Outcome and reflection",
        "goal": "Review outcomes, uncertainty and transferable learning.",
        "questions": [
            "What outcome is actually documented, and what remains unknown?",
            "Which decision in your reasoning was strongest and which was least secure?",
            "Write three transferable learning points and one question for future revision.",
        ],
        "rubric": [
            "Documented outcome distinguished from assumptions", "Uncertainty acknowledged",
            "Reasoning reviewed honestly", "Safety-critical lesson identified",
            "Transferable knowledge extracted", "Actionable learning goal defined",
        ],
        "quiz": [
            ("A published case report is most useful for:", ["Proving a treatment is superior", "Exploring a clinical presentation or diagnostic challenge", "Replacing clinical guidelines"], 1, "A single case report can teach patterns and generate questions but cannot establish comparative efficacy."),
            ("A useful reflection identifies:", ["Only the final diagnosis", "Strengths, gaps, uncertainty and an improvement goal", "Only facts already known"], 1, "Reflection should translate experience into a specific future learning action."),
            ("Synthetic patient data should be described as:", ["Real-world patient records", "Synthetic educational data", "A complete clinical history"], 1, "Synthea records are simulated and may be incomplete or simplified."),
        ],
    },
]

ILLNESS_SCRIPT_FIELDS = [
    ("Epidemiology", "Who is affected? Consider age, risk factors and setting."),
    ("Mechanism / pathophysiology", "What mechanism explains the disease?"),
    ("Time course", "Typical onset, progression and course."),
    ("Typical features", "Symptoms and examination findings that support it."),
    ("Differential diagnoses", "Important mimics and how to distinguish them."),
    ("Investigations", "First-line tests and expected patterns; cite a source."),
    ("Red flags", "Features requiring urgent assessment or escalation."),
    ("Management principles", "Current guideline-based principles, not a patient-specific prescription."),
    ("Complications / prognosis", "Important complications and outcome considerations."),
    ("References", "Guidelines, reviews or authoritative sources with dates."),
]

OSCE_STATIONS = {
    "Focused history": [
        "Introduce yourself, confirm identity and obtain consent.",
        "Establish the presenting concern and patient's agenda.",
        "Characterise the symptom: onset, location, duration, character, radiation, associations, timing and severity where relevant.",
        "Explore relevant systems, past history, medication, allergies and family/social context.",
        "Screen for red flags and summarise the history.",
        "Explain the next steps and check understanding.",
    ],
    "Acute assessment / ABCDE": [
        "Recognise immediate danger and call for help early when indicated.",
        "Assess airway, breathing, circulation, disability and exposure systematically.",
        "Identify observations requiring urgent action and reassessment.",
        "Communicate findings using a concise structured handover.",
        "Document actions, response and escalation.",
    ],
    "Focused examination": [
        "Introduce yourself, confirm identity, explain the examination and obtain consent.",
        "Check comfort, exposure, positioning and infection-prevention requirements.",
        "Use a systematic examination sequence appropriate to the station.",
        "Describe objective findings before interpretation.",
        "Summarise findings, limitations and next steps.",
    ],
    "Communication and explanation": [
        "Establish what the person understands and wants to know.",
        "Use plain language and chunk-and-check information.",
        "Discuss uncertainty honestly and respond empathetically.",
        "Use shared decision-making and confirm understanding.",
        "Agree on next steps and safety-netting.",
    ],
    "Clinical handover / SBAR": [
        "Situation: identify yourself, patient and immediate issue.",
        "Background: provide relevant clinical context.",
        "Assessment: summarise findings, concerns and uncertainty.",
        "Recommendation: state what is needed and the urgency.",
        "Confirm the receiver's understanding and document the handover.",
    ],
    "Medication counselling": [
        "Confirm the intended medicine and verify the applicable source.",
        "Explain indication, administration and expected duration as supported by a source.",
        "Discuss important adverse effects, interactions and precautions.",
        "Check understanding and adherence barriers.",
        "Explain what to do if problems occur and where to seek help.",
    ],
}

DATASET_CATALOGUE = [
    {
        "name": "Synthea CSV / FHIR",
        "purpose": "Synthetic longitudinal patients, encounters, conditions, medications, observations, procedures and care plans.",
        "url": "https://github.com/synthetichealth/synthea",
        "access": "Open-source synthetic data generator; keep generated cohorts separated and cite the generator/version.",
        "priority": "Core",
    },
    {
        "name": "Egypt National Essential Medicine List 2025 (English)",
        "purpose": "Egypt-specific essential medicines reference.",
        "url": "https://www.who.int/publications/m/item/egypt--national-essential-medicine-list-2025-%28english%29",
        "access": "Download the WHO publication; retain publication date and source.",
        "priority": "Core",
    },
    {
        "name": "Egyptian Drug Authority formulary",
        "purpose": "Egyptian formulary chapters including antimicrobial, cardiovascular, endocrine, blood, nervous system, GI and respiratory medicines.",
        "url": "https://www.edaegypt.gov.eg/en/the-regulatory-reference-of-the-egyptian-drug-authority-eda/the-egyptian-drug-formulary/",
        "access": "Use the EDA-hosted documents; confirm the current chapter and publication date.",
        "priority": "Core",
    },
    {
        "name": "Egyptian Health Council antimicrobial stewardship guidance",
        "purpose": "Antimicrobial stewardship principles and local guidance.",
        "url": "https://lms.ehc.gov.eg/lms/mod/book/view.php?chapterid=5329&id=751",
        "access": "EHC resource, last update listed as 1 June 2026; check for subsequent updates.",
        "priority": "Core",
    },
    {
        "name": "MIT-BIH Arrhythmia Database",
        "purpose": "Annotated two-channel ambulatory rhythm recordings for ECG rhythm practice.",
        "url": "https://physionet.org/content/mitdb/1.0.0/",
        "access": "ODC Attribution; cite Moody and Mark / PhysioNet. Approx. 73.5 MB compressed.",
        "priority": "Recommended",
    },
    {
        "name": "PTB-XL",
        "purpose": "Annotated 12-lead ECGs for more advanced ECG interpretation.",
        "url": "https://physionet.org/content/ptb-xl/1.0.3/",
        "access": "CC BY 4.0; cite dataset. Approx. 1.7 GB archive / 3 GB extracted.",
        "priority": "Optional large download",
    },
    {
        "name": "LOINC",
        "purpose": "Standardised identifiers for laboratory tests and clinical observations.",
        "url": "https://loinc.org/downloads/",
        "access": "Free account; use subject to LOINC licence. Version 2.83 listed Aug 2026.",
        "priority": "Recommended",
    },
    {
        "name": "MedMNIST",
        "purpose": "Small standardised biomedical image datasets for educational image-learning tasks.",
        "url": "https://medmnist.com/",
        "access": "Check the specific subset licence; DermaMNIST is CC BY-NC 4.0. Not for clinical use.",
        "priority": "Optional",
    },
    {
        "name": "Synthetic Denver Synthea cohort",
        "purpose": "Specialised paediatric growth and obesity-oriented synthetic cohort.",
        "url": "https://synthetichealth.github.io/downloads.html",
        "access": "Verify current download, version and terms before importing.",
        "priority": "Optional",
    },
    {
        "name": "Coherent Dataset",
        "purpose": "Multimodal synthetic records linking FHIR with imaging and other modalities.",
        "url": "https://synthetichealth.github.io/downloads.html",
        "access": "Large download (about 9 GB); use only with sufficient disk space and an external drive.",
        "priority": "Advanced",
    },
    {
        "name": "MIMIC-IV",
        "purpose": "Rich hospital/ICU data for advanced observational learning and research.",
        "url": "https://physionet.org/content/mimiciv/3.1/",
        "access": "Credentialed access, required human-subjects training and signed DUA. Not an immediate download.",
        "priority": "Restricted",
    },
    {
        "name": "eICU Collaborative Research Database",
        "purpose": "Multicentre critical-care data for advanced analysis.",
        "url": "https://eicu-crd.mit.edu/gettingstarted/access/",
        "access": "Credentialed access and terms apply; not an immediate download.",
        "priority": "Restricted",
    },
]


VIGNETTE_FRAMEWORKS = {
    "Chest pain": {
        "history": ["Onset, character, site, radiation, duration and provoking/relieving factors", "Dyspnoea, diaphoresis, nausea, syncope or palpitations", "Cardiovascular risk factors and relevant past history", "Thromboembolic, aortic and other dangerous alternative features"],
        "examination": ["Initial appearance and observations", "Cardiovascular and respiratory examination", "Perfusion, pulses and signs of heart failure where relevant"],
        "reasoning": ["Acute coronary syndrome", "Aortic and pulmonary vascular emergencies", "Pericardial, pulmonary, gastrointestinal and musculoskeletal causes"],
        "investigations": ["ECG and serial troponin pathway where indicated", "Targeted imaging and other tests guided by risk and findings"],
        "safety": ["Instability, ongoing severe pain, syncope, hypoxia or shock features"],
    },
    "Dyspnoea": {
        "history": ["Acute versus chronic onset and progression", "Rest/exertional symptoms, orthopnoea and paroxysmal nocturnal dyspnoea", "Wheeze, cough, sputum, fever, chest pain or haemoptysis", "Cardiac, respiratory, thromboembolic and exposure history"],
        "examination": ["Work of breathing, oxygenation and observations", "Respiratory and cardiovascular examination", "Perfusion, volume status and signs of exhaustion"],
        "reasoning": ["Airway or ventilatory emergency", "Cardiac causes", "Pulmonary infection, obstructive disease and vascular causes", "Anaemia, metabolic and other systemic causes"],
        "investigations": ["Pulse oximetry and targeted ECG/chest imaging", "Blood tests, blood gas or other tests only when clinically indicated"],
        "safety": ["Severe work of breathing, cyanosis, altered consciousness, exhaustion or haemodynamic instability"],
    },
    "Fever": {
        "history": ["Onset, duration, measured temperature and rigors", "Localising symptoms and recent infection exposure", "Travel, occupation, animal/food/water exposure where relevant", "Immune status, devices, recent procedures and medicines"],
        "examination": ["Observations and overall appearance", "Focused source-directed examination", "Hydration, perfusion, mental state and skin findings"],
        "reasoning": ["Infectious source and severity", "Sepsis or other time-critical syndromes", "Non-infectious inflammatory, drug-related and malignant causes"],
        "investigations": ["Tests targeted to likely source and severity", "Cultures and imaging based on clinical context and local pathways"],
        "safety": ["Shock, altered mental state, respiratory compromise, meningism or high-risk immune status"],
    },
    "Abdominal pain": {
        "history": ["Onset, site, character, radiation, severity and progression", "Vomiting, bowel habit, bleeding, urinary and gynaecological symptoms where relevant", "Previous surgery, medications, pregnancy possibility and comorbidity"],
        "examination": ["Observations, hydration and general appearance", "Abdominal inspection, palpation, percussion and auscultation as appropriate", "Hernial, vascular, rectal or pelvic examination only when indicated and with consent"],
        "reasoning": ["Surgical, inflammatory, vascular and obstructive causes", "Hepatobiliary, pancreatic, urinary and gynaecological causes", "Extra-abdominal mimics"],
        "investigations": ["Pregnancy test when relevant", "Targeted blood tests, urine, imaging and serial examination according to context"],
        "safety": ["Peritonism, shock, GI bleeding, severe pain out of proportion or pregnancy-related emergency features"],
    },
    "Headache": {
        "history": ["Thunderclap versus gradual onset, first/worst headache and progression", "Fever, neck stiffness, focal deficit, seizure or visual symptoms", "Trauma, pregnancy/postpartum, malignancy, immune status and anticoagulation", "Previous headache pattern and medication use"],
        "examination": ["Observations and mental state", "Focused neurological examination", "Meningism and fundoscopy when appropriate"],
        "reasoning": ["Primary headache syndromes", "Vascular, infectious, pressure-related and structural secondary causes", "Medication-overuse and other secondary causes"],
        "investigations": ["Urgent imaging or other tests guided by red flags and local pathway", "Avoid indiscriminate testing in low-risk typical presentations"],
        "safety": ["Thunderclap onset, focal neurological deficit, fever/meningism, altered consciousness or pregnancy/postpartum red flags"],
    },
    "Syncope": {
        "history": ["Circumstances, posture, exertion and prodrome", "Witness account, duration, recovery and injuries", "Palpitations, chest pain, dyspnoea and family history of sudden death", "Medicines, volume loss and relevant cardiac/neurological history"],
        "examination": ["Observations and cardiovascular examination", "Orthostatic measurements when appropriate", "Focused neurological and injury assessment"],
        "reasoning": ["Reflex and orthostatic causes", "Cardiac arrhythmia or structural disease", "Seizure and other mimics"],
        "investigations": ["12-lead ECG and targeted tests", "Further monitoring or imaging guided by risk"],
        "safety": ["Exertional or supine syncope, abnormal ECG, structural heart disease, family sudden death or haemodynamic compromise"],
    },
    "Acute focal weakness": {
        "history": ["Exact onset and last-known-well time", "Face, arm, speech, vision, balance and sensory symptoms", "Fluctuation, progression, seizure or headache", "Anticoagulants, vascular risk factors and prior neurological history"],
        "examination": ["ABCDE and immediate glucose", "Focused neurological examination and disability assessment", "Swallowing, airway protection and baseline function where possible"],
        "reasoning": ["Stroke/TIA and haemorrhage", "Seizure/post-ictal deficit and metabolic mimics", "Other neurological and structural causes"],
        "investigations": ["Urgent stroke pathway and imaging according to local protocol", "Targeted blood tests and ECG without delaying time-critical care"],
        "safety": ["Treat as time-critical; establish last-known-well and activate the local emergency pathway"],
    },
    "Hot swollen joint": {
        "history": ["Acute versus chronic onset; monoarticular or polyarticular", "Fever, systemic illness, trauma and ability to bear weight", "Previous gout, inflammatory disease, prosthesis, skin infection or immune suppression"],
        "examination": ["Observations and systemic appearance", "Joint warmth, erythema, swelling, range of motion and adjacent skin", "Other joint and systemic examination as indicated"],
        "reasoning": ["Septic arthritis must be considered urgently", "Crystal arthritis, inflammatory disease and trauma", "Other infectious and periarticular causes"],
        "investigations": ["Urgent aspiration and microbiology when septic arthritis is suspected", "Blood tests and imaging as adjuncts, not replacements for indicated aspiration"],
        "safety": ["Sepsis, prosthetic joint, immune suppression or a painful hot joint with restricted movement"],
    },
}
