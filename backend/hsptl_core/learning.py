"""Short, source-linked clinical microlearning packs for HSPTL.

Questions are curated educational material, not generated from patient diagnoses
as if the synthetic record were a clinical guideline. Case matching only selects
relevant learning packs; it never establishes a diagnosis.
"""
from __future__ import annotations

from typing import Any

QUESTION_PACKS: dict[str, dict[str, Any]] = {
    "type_2_diabetes": {
        "title": "Type 2 diabetes: HbA1c and individualised targets",
        "tagline": "Interpret monitoring in context; targets are not one-size-fits-all.",
        "summary": "NICE recommends tailoring HbA1c monitoring to stability and therapy: every 3–6 months until stable, then every 6 months once stable. Targets should be agreed with the person and adjusted for treatment risks and individual circumstances.",
        "keywords": ["type 2 diabetes", "diabetes mellitus", "diabetes", "hyperglycaemia", "hyperglycemia"],
        "source_title": "NICE NG28: Type 2 diabetes in adults (updated 18 February 2026)",
        "source_url": "https://www.nice.org.uk/guidance/ng28/chapter/Blood-glucose-management",
        "questions": [
            {"question": "For an adult with type 2 diabetes whose HbA1c is not yet stable on an unchanged regimen, how often does NICE recommend measuring HbA1c?", "options": ["Every 3–6 months, tailored to need", "Only once every 5 years", "Every week for everyone"], "answer": 0, "explanation": "NICE recommends HbA1c every 3 to 6 months until stable on unchanging therapy, then every 6 months once stable.", "takeaway": "Monitoring frequency depends on stability and the clinical situation."},
            {"question": "How should an HbA1c target be selected in type 2 diabetes?", "options": ["Use one identical target for every adult", "Agree an individual target, considering treatment benefits, risks and preferences", "Choose the lowest possible number regardless of hypoglycaemia"], "answer": 1, "explanation": "NICE recommends discussing and agreeing an individual HbA1c target; hypoglycaemia risk, frailty, comorbidity and quality of life can affect the target.", "takeaway": "Individualise targets; avoid treating a number in isolation."},
            {"question": "When may HbA1c be unreliable for monitoring glycaemia?", "options": ["When erythrocyte turnover is disturbed or haemoglobin type is abnormal", "Whenever a patient is over 40", "Only when blood pressure is elevated"], "answer": 0, "explanation": "NICE advises alternative measures such as quality-controlled plasma glucose profiles or fructosamine when disturbed erythrocyte turnover or abnormal haemoglobin makes HbA1c invalid.", "takeaway": "Check whether the biomarker is valid before interpreting its trend."},
        ],
    },
    "copd": {
        "title": "COPD: confirming the diagnosis",
        "tagline": "Use appropriate post-bronchodilator spirometry and clinical context.",
        "summary": "NICE recommends post-bronchodilator spirometry to confirm COPD. Interpret the ratio alongside symptoms and clinical context; a spirometry value should not be detached from the patient's presentation.",
        "keywords": ["copd", "chronic obstructive pulmonary", "emphysema", "chronic bronchitis"],
        "source_title": "NICE NG115: COPD in over 16s",
        "source_url": "https://www.nice.org.uk/guidance/NG115/chapter/recommendations",
        "questions": [
            {"question": "Which test does NICE recommend to confirm COPD?", "options": ["Peak flow diary alone", "Post-bronchodilator spirometry", "Chest radiograph alone"], "answer": 1, "explanation": "NICE recommends post-bronchodilator spirometry to confirm COPD.", "takeaway": "COPD diagnosis requires appropriate spirometric confirmation."},
            {"question": "An older adult has an FEV1/FVC ratio below 0.7 but lacks typical COPD symptoms. What does NICE advise considering?", "options": ["Alternative diagnoses or further investigations", "COPD is certain without further context", "Ignore the result completely"], "answer": 0, "explanation": "NICE advises considering alternative diagnoses or investigations in older people with a ratio below 0.7 but without typical symptoms.", "takeaway": "Interpret spirometry in the context of age and symptoms."},
            {"question": "What is an important role of spirometry after diagnosis?", "options": ["It is never repeated", "Reconsider diagnosis when appropriate and monitor progression", "It replaces history and examination"], "answer": 1, "explanation": "NICE recommends spirometry at diagnosis, to reconsider diagnosis in selected circumstances, and to monitor disease progression.", "takeaway": "Use spirometry as part of longitudinal assessment, not as a standalone answer."},
        ],
    },
    "heart_failure": {
        "title": "Heart failure: diagnostic work-up",
        "tagline": "Natriuretic peptides guide referral; echocardiography characterises function.",
        "summary": "NICE recommends NT-proBNP measurement in people with suspected heart failure and transthoracic echocardiography as part of specialist assessment. Natriuretic peptide results require context and do not identify ejection-fraction phenotype on their own.",
        "keywords": ["heart failure", "cardiac failure", "congestive heart failure"],
        "source_title": "NICE NG106: Chronic heart failure in adults (updated 2025)",
        "source_url": "https://www.nice.org.uk/guidance/ng106/chapter/Recommendations",
        "questions": [
            {"question": "Which blood test does NICE recommend in people with suspected chronic heart failure?", "options": ["NT-proBNP", "D-dimer in every patient", "Troponin as the sole diagnostic test"], "answer": 0, "explanation": "NICE recommends measuring NT-proBNP in people with suspected heart failure to guide referral and investigation.", "takeaway": "Use natriuretic peptide testing within a structured diagnostic pathway."},
            {"question": "In an untreated person, what does NT-proBNP below 400 ng/L generally suggest according to NICE?", "options": ["Heart failure is less likely, but clinical context still matters", "Heart failure is definitely present", "The result proves a normal echocardiogram"], "answer": 0, "explanation": "NICE says a level below 400 ng/L in an untreated person makes a diagnosis less likely; consider alternative causes and seek specialist discussion if concern remains.", "takeaway": "A low result changes probability; it does not replace clinical assessment."},
            {"question": "What does transthoracic echocardiography help assess in suspected heart failure?", "options": ["Only coronary artery plaque", "Valve disease and systolic/diastolic ventricular function", "Only lung volumes"], "answer": 1, "explanation": "NICE recommends echocardiography to exclude important valve disease and assess systolic and diastolic ventricular function.", "takeaway": "Echocardiography characterises cardiac structure and function."},
        ],
    },
    "chronic_kidney_disease": {
        "title": "Chronic kidney disease: defining and classifying CKD",
        "tagline": "Chronicity matters; classify using both eGFR and albuminuria.",
        "summary": "NICE defines CKD by abnormalities of kidney function or structure present for more than 3 months. Classification uses both estimated GFR and urine albumin:creatinine ratio (ACR). A single low eGFR needs confirmation and assessment for acute deterioration.",
        "keywords": ["chronic kidney disease", "ckd", "chronic renal insufficiency"],
        "source_title": "NICE NG203: Chronic kidney disease",
        "source_url": "https://www.nice.org.uk/guidance/ng203/chapter/recommendations",
        "questions": [
            {"question": "What is central to the definition of chronic kidney disease?", "options": ["Any single abnormal creatinine result", "Abnormalities of kidney function or structure persisting for more than 3 months", "A single episode of dehydration"], "answer": 1, "explanation": "NICE defines CKD by kidney-function or structural abnormalities present for more than 3 months, with implications for health.", "takeaway": "Chronicity distinguishes CKD from a transient or acute abnormality."},
            {"question": "How does NICE classify CKD?", "options": ["By serum creatinine alone", "By eGFR and albumin:creatinine ratio (ACR)", "By age alone"], "answer": 1, "explanation": "NICE uses GFR categories (G1–G5) and ACR categories (A1–A3).", "takeaway": "Think GFR and albuminuria together."},
            {"question": "An adult has a newly identified eGFR below 60 mL/min/1.73 m² and no previous baseline. What does NICE recommend initially?", "options": ["Repeat within 2 weeks to confirm and exclude acute deterioration", "Label CKD immediately without repeat testing", "Ignore if asymptomatic"], "answer": 0, "explanation": "NICE recommends repeating an eGFR below 60 within 2 weeks in an adult not previously tested, and considers biological/analytical variability.", "takeaway": "Confirm unexpected renal changes and consider AKI before labelling chronic disease."},
        ],
    },
    "iron_deficiency_anaemia": {
        "title": "Iron-deficiency anaemia: confirmation and cause",
        "tagline": "Confirm iron deficiency and look for the underlying cause.",
        "summary": "The British Society of Gastroenterology guideline identifies ferritin as the single most useful marker of iron-deficiency anaemia, while noting that inflammation can produce a falsely normal ferritin. In adults with newly diagnosed IDA without an obvious explanation, gastrointestinal pathology should be considered.",
        "keywords": ["iron deficiency anaemia", "iron deficiency anemia", "iron deficiency"],
        "source_title": "British Society of Gastroenterology guideline for iron-deficiency anaemia in adults (2021)",
        "source_url": "https://gut.bmj.com/content/70/11/2030",
        "questions": [
            {"question": "Which test is described as the single most useful marker of iron-deficiency anaemia?", "options": ["Serum ferritin", "Serum sodium", "Troponin"], "answer": 0, "explanation": "The BSG guideline identifies serum ferritin as the single most useful marker, while noting transferrin saturation can help if a false-normal ferritin is suspected.", "takeaway": "Interpret ferritin in the context of inflammation and other iron studies."},
            {"question": "Why can ferritin be misleading in a patient with inflammation?", "options": ["It is an acute-phase protein and may be apparently normal despite iron deficiency", "It always falls to zero", "It is unaffected by inflammation"], "answer": 0, "explanation": "Ferritin is an acute-phase protein; inflammatory disease can produce a normal-looking level despite iron deficiency.", "takeaway": "A normal ferritin does not always exclude iron deficiency when inflammation is present."},
            {"question": "In an adult with newly diagnosed iron-deficiency anaemia without an obvious explanation, what should be considered?", "options": ["Only dietary advice without further assessment", "Potential gastrointestinal pathology and appropriate investigation", "Assume the cause is inherited"], "answer": 1, "explanation": "The BSG guideline notes that IDA can arise from gastrointestinal pathology, including malignancy, and advises considering GI investigation in adults without an obvious explanation.", "takeaway": "Identify the cause of iron deficiency rather than treating the blood count alone."},
        ],
    },
    "record_literacy": {
        "title": "Reading a clinical record",
        "tagline": "Separate documented facts from assumptions.",
        "summary": "A patient record is an extract of coded events, not a complete clinical encounter. Missing fields are unknown, historical prescriptions may not be current, and a coded condition still needs clinical context.",
        "keywords": [],
        "source_title": "HSPTL data interpretation principles",
        "source_url": "",
        "questions": [
            {
                "question": "An observation row exists, but its numeric result is blank. What can you conclude?",
                "options": ["The result was normal", "The result was abnormal", "The result is unavailable in this extract"],
                "answer": 2,
                "explanation": "A record with no readable value is not interpretable. Do not convert missing data into a normal or abnormal finding.",
                "takeaway": "Missing is not normal. Check the source record and context.",
            },
            {
                "question": "A medication request was authored several years before the latest encounter. What is the safest interpretation?",
                "options": ["The patient is definitely taking it now", "It is a historical prescription record; current use needs verification", "It should automatically be renewed"],
                "answer": 1,
                "explanation": "An old medication request does not establish current use, adherence, indication or ongoing suitability.",
                "takeaway": "Always reconcile current medicines; don't infer them from old requests.",
            },
            {
                "question": "A coded condition appears in a synthetic EHR extract. What does that establish?",
                "options": ["That the code is present in the source record", "That the diagnosis has been independently confirmed", "That every symptom is explained"],
                "answer": 0,
                "explanation": "It establishes that the condition code is recorded. It does not provide a complete history, examination or independent diagnostic validation.",
                "takeaway": "Describe coded conditions as recorded entries, then reason from the available evidence.",
            },
        ],
    },
    "oral_health": {
        "title": "Oral health: caries and gingival disease",
        "tagline": "Understand the plaque–sugar pathway and periodontal findings.",
        "summary": "Dental caries develops when plaque converts free sugars into acids that progressively damage tooth structure. Gingivitis commonly presents with swollen or bleeding gums. Free-sugar intake, fluoride exposure and effective plaque removal are important modifiable factors.",
        "keywords": ["dental caries", "caries", "gingivitis", "periodontal", "tooth decay", "dental infection", "dental"],
        "source_title": "WHO: Oral health (17 March 2025)",
        "source_url": "https://www.who.int/news-room/fact-sheets/detail/oral-health",
        "questions": [
            {
                "question": "Which mechanism best describes the development of dental caries?",
                "options": ["Plaque converts free sugars into acids that damage tooth structure", "Gingival inflammation directly dissolves enamel", "Saliva normally converts fluoride into dental plaque"],
                "answer": 0,
                "explanation": "WHO describes how plaque bacteria metabolise free sugars to acids, which damage teeth over time.",
                "takeaway": "Caries is a biofilm- and sugar-mediated disease; consider diet, fluoride and plaque control.",
            },
            {
                "question": "Which combination contains important modifiable caries risk factors?",
                "options": ["Free-sugar intake, inadequate fluoride exposure and poor plaque removal", "Eye strain, low water temperature and exercise frequency", "Age alone, with no modifiable factors"],
                "answer": 0,
                "explanation": "WHO identifies free sugars, inadequate fluoride exposure and lack of plaque removal by toothbrushing as important contributors.",
                "takeaway": "Prevention needs more than a filling: address sugar exposure, fluoride and oral hygiene.",
            },
            {
                "question": "Which clinical features are characteristic of gingivitis in the WHO oral-health fact sheet?",
                "options": ["Bleeding or swollen gums", "Painless jaundice", "Unilateral calf swelling"],
                "answer": 0,
                "explanation": "WHO describes gingivitis as bleeding or swollen gums; periodontal disease can also involve pain and sometimes bad breath.",
                "takeaway": "Ask about bleeding, swelling, pain, oral hygiene and relevant risk factors.",
            },
        ],
    },
    "otitis_media": {
        "title": "Acute otitis media in children",
        "tagline": "Natural history, reassessment and complications.",
        "summary": "NICE describes acute otitis media as commonly self-limiting. Symptoms often last around 3 days and can last up to a week; viruses and bacteria may both be involved and can be difficult to distinguish clinically.",
        "keywords": ["otitis media", "otitis", "ear infection"],
        "source_title": "NICE NG91: Otitis media (acute), recommendations",
        "source_url": "https://www.nice.org.uk/guidance/ng91/chapter/recommendations",
        "questions": [
            {
                "question": "What is the usual course of acute otitis media described by NICE?",
                "options": ["It is always persistent for several months", "Symptoms commonly last about 3 days and may last up to a week", "It always requires hospital admission"],
                "answer": 1,
                "explanation": "NICE states that symptoms usually last about 3 days, sometimes up to a week, and most children improve within 3 days without antibiotics.",
                "takeaway": "Know the expected course and provide clear reassessment advice when symptoms worsen or fail to improve.",
            },
            {
                "question": "Which is an acute complication that NICE identifies as a reason for hospital referral in a child with acute otitis media?",
                "options": ["Mastoiditis", "Seasonal allergic rhinitis", "Uncomplicated wax accumulation"],
                "answer": 0,
                "explanation": "NICE includes mastoiditis, meningitis, intracranial abscess, sinus thrombosis and facial nerve paralysis among acute complications requiring hospital referral.",
                "takeaway": "Recognise local and intracranial complications; do not treat deterioration as routine.",
            },
            {
                "question": "Can the causative organism of acute otitis media always be distinguished as viral or bacterial from symptoms alone?",
                "options": ["Yes, the distinction is always obvious", "No; viruses and bacteria may both be involved and can be difficult to distinguish", "Only the presence of fever distinguishes them"],
                "answer": 1,
                "explanation": "NICE notes that acute otitis media can be viral or bacterial and that distinguishing them is difficult; both may be present at the same time.",
                "takeaway": "Avoid overconfidence in assigning a microbial cause from a limited vignette.",
            },
        ],
    },
    "sore_throat": {
        "title": "Acute sore throat and pharyngitis",
        "tagline": "Natural history, structured assessment and complications.",
        "summary": "NICE describes acute sore throat, including pharyngitis and tonsillitis, as usually self-limiting and often viral. Symptoms commonly resolve in about a week. FeverPAIN or Centor can help identify people more likely to benefit from antibiotics.",
        "keywords": ["pharyngitis", "tonsillitis", "sore throat", "throat infection"],
        "source_title": "NICE NG84: Sore throat (acute), recommendations",
        "source_url": "https://www.nice.org.uk/guidance/ng84/chapter/recommendations",
        "questions": [
            {
                "question": "What is the typical course of acute sore throat described by NICE?",
                "options": ["Most cases improve within about one week", "All cases require antibiotics", "Symptoms normally persist for months"],
                "answer": 0,
                "explanation": "NICE states that acute sore throat is often self-limiting, commonly viral, and usually improves within around one week.",
                "takeaway": "Natural history matters: not every sore throat benefits from an antibiotic.",
            },
            {
                "question": "Which structured scores does NICE recommend considering to identify people more likely to benefit from antibiotics?",
                "options": ["CHA₂DS₂-VASc and HAS-BLED", "FeverPAIN or Centor", "Wells and PERC"],
                "answer": 1,
                "explanation": "NICE recommends using FeverPAIN or Centor criteria as part of assessment. They support, rather than replace, clinical judgement.",
                "takeaway": "Choose a tool validated for the clinical question; do not mix scores from unrelated conditions.",
            },
            {
                "question": "Which presentation is a reason for hospital referral in the NICE sore-throat guidance?",
                "options": ["Mild throat discomfort with normal oral intake", "Severe systemic infection or a serious suppurative complication such as quinsy", "A brief cough without other concerning features"],
                "answer": 1,
                "explanation": "NICE recommends hospital referral for severe systemic infection or severe suppurative complications, including quinsy and deep-neck infections.",
                "takeaway": "Actively assess for serious systemic illness and suppurative complications.",
            },
        ],
    },
    "asthma": {
        "title": "Asthma: confirming the diagnosis",
        "tagline": "History is important; symptoms alone are not enough.",
        "summary": "The BTS/NICE/SIGN guideline says asthma should not be confirmed without a suggestive clinical history and a supporting objective test. Ask about wheeze, cough, breathlessness, chest tightness, variability, triggers and alternative diagnoses.",
        "keywords": ["asthma", "wheeze"],
        "source_title": "NICE NG245: Asthma diagnosis and management",
        "source_url": "https://www.nice.org.uk/guidance/ng245/chapter/Recommendations",
        "questions": [
            {
                "question": "What is required before confirming a diagnosis of asthma under the BTS/NICE/SIGN guidance?",
                "options": ["A suggestive clinical history and a supporting objective test", "A single symptom of cough", "A family history alone"],
                "answer": 0,
                "explanation": "The guideline says not to confirm asthma without a suggestive clinical history and supporting objective testing.",
                "takeaway": "Use history to establish suspicion, then seek objective evidence of variable airflow limitation or another supporting test.",
            },
            {
                "question": "Which history is most relevant when asthma is suspected?",
                "options": ["Wheeze, cough, breathlessness or chest tightness and their variation/triggers", "Only the patient's blood group", "Only a remote diagnosis without symptom review"],
                "answer": 0,
                "explanation": "NICE recommends a structured history including symptoms, variability, triggers, atopy/family history and alternative diagnoses.",
                "takeaway": "Characterise pattern and triggers, and consider alternative explanations.",
            },
            {
                "question": "Can a normal physical examination alone exclude asthma?",
                "options": ["Yes, always", "No; a normal examination does not rule it out", "Only if the patient is younger than 16"],
                "answer": 1,
                "explanation": "NICE notes that even with normal examination results, the person may still have asthma.",
                "takeaway": "A normal examination between symptomatic episodes does not settle the diagnosis.",
            },
        ],
    },
    "hypertension": {
        "title": "Hypertension: confirming raised blood pressure",
        "tagline": "Do not diagnose from one isolated clinic reading.",
        "summary": "NICE recommends repeat clinic measurement and, for clinic readings in the diagnostic range, ambulatory blood pressure monitoring to confirm hypertension. Home monitoring can be used when ABPM is unsuitable or not tolerated.",
        "keywords": ["hypertension", "high blood pressure"],
        "source_title": "NICE NG136: Hypertension in adults",
        "source_url": "https://www.nice.org.uk/guidance/ng136/chapter/recommendations",
        "questions": [
            {
                "question": "A clinic blood pressure is raised. What does NICE recommend to confirm hypertension when the clinic reading is between 140/90 and 180/120 mmHg?",
                "options": ["Diagnose from that single value", "Offer ambulatory blood pressure monitoring", "Ignore the reading if the patient feels well"],
                "answer": 1,
                "explanation": "NICE recommends ABPM to confirm a diagnosis in this clinic range; HBPM can be offered if ABPM is unsuitable or not tolerated.",
                "takeaway": "A raised clinic value needs confirmation; follow the locally applicable guideline.",
            },
            {
                "question": "If the first and second clinic blood pressure measurements differ substantially, what does NICE advise?",
                "options": ["Take a third measurement", "Use the highest value automatically", "Stop measuring"],
                "answer": 0,
                "explanation": "NICE recommends a third measurement when the second is substantially different from the first, then recording the lower of the last two.",
                "takeaway": "Measurement technique and repeat readings affect interpretation.",
            },
            {
                "question": "If ABPM is unsuitable or the person cannot tolerate it, what alternative does NICE identify?",
                "options": ["No further assessment", "Home blood pressure monitoring", "An ECG as a direct replacement for blood pressure measurement"],
                "answer": 1,
                "explanation": "NICE recommends home blood pressure monitoring as an alternative where ABPM is unsuitable or not tolerated.",
                "takeaway": "Confirm readings with an appropriate out-of-office method.",
            },
        ],
    },
    "pneumonia": {
        "title": "Community-acquired pneumonia: adult severity assessment",
        "tagline": "Use severity tools alongside clinical judgement.",
        "summary": "NICE recommends CRB65 to assess mortality risk in adults with community-acquired pneumonia in primary care, and CURB65 in hospital. Severity scores supplement clinical judgement; they do not replace assessment for cardiorespiratory failure or sepsis.",
        "keywords": ["pneumonia", "lower respiratory infection"],
        "source_title": "NICE NG250: Pneumonia diagnosis and management",
        "source_url": "https://www.nice.org.uk/guidance/ng250/chapter/Recommendations",
        "questions": [
            {
                "question": "Which components make up CRB65 for adults with community-acquired pneumonia in primary care?",
                "options": ["Confusion, respiratory rate ≥30, low blood pressure, age ≥65", "Cough, rash, bleeding, temperature", "Creatinine, heart rate, oxygen, pain"],
                "answer": 0,
                "explanation": "CRB65 assigns one point for confusion, respiratory rate 30/min or more, low blood pressure and age 65 years or older.",
                "takeaway": "Know the variables and setting for the severity tool; assess the patient as a whole.",
            },
            {
                "question": "Which score does NICE identify for adult community-acquired pneumonia in hospital?",
                "options": ["Centor", "CURB65", "CHA₂DS₂-VASc"],
                "answer": 1,
                "explanation": "NICE recommends CURB65 for adult hospital assessment; CRB65 is used in primary care.",
                "takeaway": "The setting matters when choosing a severity score.",
            },
            {
                "question": "Should a severity score override clinical judgement when cardiorespiratory failure or sepsis is suspected?",
                "options": ["Yes, always", "No; clinical judgement and signs of serious illness remain essential", "Only for patients older than 65"],
                "answer": 1,
                "explanation": "NICE explicitly advises combining severity scoring with clinical judgement and referring when features suggest serious illness such as cardiorespiratory failure or sepsis.",
                "takeaway": "A score supports judgement; it does not replace recognition of serious illness.",
            },
        ],
    },
}


def case_topic_text(case: dict[str, Any]) -> str:
    """Collect only recorded condition/encounter terminology for topic matching."""
    values: list[str] = []
    for resource in ("Condition", "Encounter"):
        frame = case.get("episode", {}).get(resource)
        if frame is None:
            continue
        try:
            for _, row in frame.iterrows():
                for column in ("code.text", "code.coding.display", "reasonCode", "type", "description"):
                    value = str(row.get(column, "") or "").strip()
                    if value and value.casefold() not in {"nan", "none", "null"}:
                        values.append(value)
        except (AttributeError, TypeError):
            continue
    return " ".join(values).casefold()


def packs_for_case(case: dict[str, Any]) -> list[str]:
    """Return one best-match pack followed by general record-literacy practice."""
    text = case_topic_text(case)
    matches = []
    for key, pack in QUESTION_PACKS.items():
        if key == "record_literacy":
            continue
        if any(keyword in text for keyword in pack["keywords"]):
            matches.append(key)
    return matches + ["record_literacy"] if matches else ["record_literacy"]
