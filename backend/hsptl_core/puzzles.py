"""Curated, fictional progressive clinical puzzles for HSPTL.

Each case is a teaching vignette, not a real patient record. Sources are linked
for further reading. The clues are intentionally staged and simplified.
"""
from __future__ import annotations

from typing import Any

PUZZLES: list[dict[str, Any]] = [
    {
        "id": "asthma-001", "specialty": "Respiratory", "difficulty": "Foundation",
        "answer": "Asthma", "aliases": ["bronchial asthma"],
        "clues": [
            "A 19-year-old student describes repeated episodes of wheeze and breathlessness.",
            "Symptoms vary over time; there are periods when breathing feels completely normal.",
            "Cough and chest tightness are more noticeable at night and after exercise.",
            "Cold air and exposure to dust can trigger episodes.",
            "The clinical history is suggestive, but the diagnosis still needs objective testing.",
            "Spirometry demonstrates variable expiratory airflow limitation with bronchodilator reversibility.",
        ],
        "explanation": "The variable, episodic symptoms and objective evidence of variable expiratory airflow limitation support asthma. A suggestive history alone should not be treated as confirmation; objective testing is important.",
        "takeaways": [
            "Ask about variability, night-time symptoms and triggers.",
            "Do not confirm asthma from symptoms alone when objective testing is available.",
            "A normal examination between episodes does not by itself exclude asthma.",
        ],
        "source_title": "BTS/NICE/SIGN guideline NG245: Asthma diagnosis and management",
        "source_url": "https://www.nice.org.uk/guidance/ng245/chapter/Recommendations",
    },
    {
        "id": "copd-001", "specialty": "Respiratory", "difficulty": "Intermediate",
        "answer": "Chronic obstructive pulmonary disease", "aliases": ["copd", "chronic obstructive lung disease"],
        "clues": [
            "A 68-year-old former smoker reports gradually progressive breathlessness.",
            "The breathlessness is persistent rather than occurring only in brief, isolated attacks.",
            "There is a longstanding cough with sputum production.",
            "The patient has a substantial cumulative tobacco exposure.",
            "Spirometry is performed after bronchodilator administration.",
            "Post-bronchodilator FEV1/FVC is below 0.70 in the context of compatible symptoms and risk factors.",
        ],
        "explanation": "Persistent airflow obstruction on post-bronchodilator spirometry, interpreted alongside compatible symptoms and exposure history, supports COPD. The ratio should not be interpreted in isolation.",
        "takeaways": [
            "Confirm COPD with post-bronchodilator spirometry.",
            "Interpret spirometry with symptoms, exposures and clinical context.",
            "Consider alternative explanations when symptoms and spirometry do not fit.",
        ],
        "source_title": "NICE NG115: COPD in over 16s",
        "source_url": "https://www.nice.org.uk/guidance/ng115/chapter/recommendations",
    },
    {
        "id": "heart-failure-001", "specialty": "Cardiology", "difficulty": "Intermediate",
        "answer": "Heart failure", "aliases": ["congestive heart failure", "chronic heart failure"],
        "clues": [
            "A 72-year-old reports gradually worsening exertional breathlessness.",
            "They now need extra pillows to sleep comfortably because lying flat worsens breathlessness.",
            "Examination identifies bilateral ankle oedema and bibasal crackles.",
            "A natriuretic peptide test is above the relevant referral threshold.",
            "Transthoracic echocardiography is arranged as part of specialist assessment.",
            "The echocardiogram demonstrates impaired left ventricular systolic function.",
        ],
        "explanation": "The symptom pattern, signs of congestion, natriuretic peptide result and echocardiographic abnormality support heart failure. Natriuretic peptide alone does not identify the ejection-fraction phenotype.",
        "takeaways": [
            "Ask about exertional dyspnoea, orthopnoea and paroxysmal nocturnal dyspnoea.",
            "Look for signs of congestion, but remember that no single sign is diagnostic.",
            "Echocardiography characterises cardiac structure and function.",
        ],
        "source_title": "NICE NG106: Chronic heart failure in adults",
        "source_url": "https://www.nice.org.uk/guidance/ng106/chapter/Recommendations",
    },
    {
        "id": "ckd-001", "specialty": "Renal", "difficulty": "Intermediate",
        "answer": "Chronic kidney disease", "aliases": ["ckd", "chronic renal disease", "chronic renal impairment"],
        "clues": [
            "A 61-year-old is found to have a reduced estimated glomerular filtration rate on routine blood testing.",
            "There are no acute symptoms suggesting a sudden illness.",
            "A urine albumin-to-creatinine ratio is also abnormal.",
            "Repeat testing continues to show kidney-function abnormalities after three months.",
            "The abnormalities are therefore persistent rather than a single isolated result.",
            "The condition is classified using both eGFR and urine ACR categories.",
        ],
        "explanation": "Chronic kidney disease is defined by abnormalities of kidney function or structure present for more than three months. Classification uses both eGFR and albuminuria; a single low eGFR needs confirmation and clinical context.",
        "takeaways": [
            "Chronicity matters: do not label CKD from one isolated result.",
            "Use both eGFR and urine ACR to classify risk.",
            "Consider acute kidney injury and reversible causes when abnormalities are newly detected.",
        ],
        "source_title": "NICE NG203: Chronic kidney disease",
        "source_url": "https://www.nice.org.uk/guidance/ng203/chapter/recommendations",
    },
    {
        "id": "ida-001", "specialty": "Haematology", "difficulty": "Foundation",
        "answer": "Iron-deficiency anaemia", "aliases": ["iron deficiency anemia", "ida", "iron deficiency"],
        "clues": [
            "A 34-year-old reports several months of fatigue and reduced exercise tolerance.",
            "A full blood count shows a reduced haemoglobin concentration.",
            "The red cells are smaller than expected and the MCH is reduced.",
            "Serum ferritin is clearly reduced.",
            "The history is reviewed for blood loss, diet, malabsorption and other possible causes.",
            "The overall pattern supports depleted iron stores causing anaemia.",
        ],
        "explanation": "Low haemoglobin with microcytosis/hypochromia and a low ferritin supports iron-deficiency anaemia. Ferritin is the most useful single marker, but inflammation can make it appear falsely normal.",
        "takeaways": [
            "Ferritin is the most useful single marker of iron deficiency in many settings.",
            "A normal ferritin does not always exclude deficiency when inflammation is present.",
            "Identify and investigate the cause rather than treating the laboratory result alone.",
        ],
        "source_title": "British Society of Gastroenterology guideline: iron-deficiency anaemia in adults",
        "source_url": "https://gut.bmj.com/content/70/11/2030",
    },
    {
        "id": "hypertension-001", "specialty": "Cardiology", "difficulty": "Foundation",
        "answer": "Hypertension", "aliases": ["high blood pressure", "raised blood pressure"],
        "clues": [
            "A 52-year-old has an elevated blood pressure reading during a routine clinic visit.",
            "They feel well and have no symptoms that reliably establish the diagnosis.",
            "The measurement is repeated using an appropriate technique.",
            "Clinic readings remain in the range where confirmation with out-of-office measurement is recommended.",
            "Ambulatory blood pressure monitoring is arranged.",
            "The average out-of-office readings confirm persistently raised blood pressure.",
        ],
        "explanation": "Hypertension is confirmed using repeated and, where indicated, out-of-office blood-pressure measurement. A single elevated clinic reading is not enough for most routine diagnostic decisions.",
        "takeaways": [
            "Use correct measurement technique and repeat clinic measurements.",
            "ABPM is recommended to confirm many raised clinic readings.",
            "Symptoms are often absent; diagnosis depends on measurement, not how the person feels.",
        ],
        "source_title": "NICE NG136: Hypertension in adults",
        "source_url": "https://www.nice.org.uk/guidance/ng136/chapter/recommendations",
    },
    {
        "id": "cap-001", "specialty": "Respiratory", "difficulty": "Intermediate",
        "answer": "Community-acquired pneumonia", "aliases": ["pneumonia", "cap", "community acquired pneumonia"],
        "clues": [
            "A 46-year-old develops an acute illness with cough and fever.",
            "They report pleuritic chest discomfort and feel generally unwell.",
            "Respiratory rate is elevated and oxygen saturation is lower than expected.",
            "Chest examination identifies focal crackles over one lung region.",
            "Chest radiography demonstrates a new focal air-space opacity consistent with infection.",
            "The clinician uses a severity assessment alongside clinical judgement to guide the setting of care.",
        ],
        "explanation": "The acute infectious presentation and new focal radiographic change support community-acquired pneumonia. Severity scores support assessment but do not replace judgement about cardiorespiratory failure or sepsis.",
        "takeaways": [
            "Assess oxygenation, respiratory rate and physiological instability.",
            "Use CRB65 in primary care or CURB65 in hospital where appropriate.",
            "Do not allow a low score to override serious clinical features.",
        ],
        "source_title": "NICE NG250: Pneumonia diagnosis and management",
        "source_url": "https://www.nice.org.uk/guidance/ng250/chapter/Recommendations",
    },
    {
        "id": "aom-001", "specialty": "Paediatrics", "difficulty": "Foundation",
        "answer": "Acute otitis media", "aliases": ["aom", "middle ear infection", "acute middle ear infection"],
        "clues": [
            "A 3-year-old becomes unsettled and develops ear pain over one day.",
            "The child has a recent upper respiratory tract infection.",
            "Temperature is raised and the child is less interested in food.",
            "Otoscopy shows a bulging tympanic membrane with evidence of middle-ear effusion.",
            "There is no post-auricular swelling or displacement of the pinna.",
            "The findings support an acute infection of the middle ear; most uncomplicated episodes are self-limiting.",
        ],
        "explanation": "Acute onset of ear symptoms with a bulging tympanic membrane and middle-ear effusion supports acute otitis media. Consider complications such as mastoiditis when red flags are present.",
        "takeaways": [
            "Otoscopy is central to assessment; symptoms alone are not enough.",
            "Many uncomplicated episodes improve without antibiotics.",
            "Recognise complications and features requiring referral.",
        ],
        "source_title": "NICE NG91: Otitis media (acute) in under 12s",
        "source_url": "https://www.nice.org.uk/guidance/ng91/chapter/recommendations",
    },
    {
        "id": "sore-throat-001", "specialty": "Infectious diseases", "difficulty": "Foundation",
        "answer": "Acute viral pharyngitis", "aliases": ["viral pharyngitis", "viral sore throat", "acute sore throat", "pharyngitis"],
        "clues": [
            "A 22-year-old presents with a three-day history of sore throat.",
            "They also have cough and coryzal symptoms.",
            "The throat is erythematous, without a peritonsillar swelling or uvular deviation.",
            "There is no drooling, stridor, respiratory distress or inability to swallow fluids.",
            "The overall pattern is more consistent with a self-limiting viral illness than a high-likelihood bacterial infection.",
            "The educational working diagnosis is acute viral pharyngitis; red flags and clinical context still matter.",
        ],
        "explanation": "Most acute sore throats are self-limiting and often viral. Cough and coryzal symptoms support a viral pattern, but the clinician must assess severity and red flags. FeverPAIN or Centor can support antibiotic decisions when appropriate.",
        "takeaways": [
            "Most acute sore throats are self-limiting.",
            "Use FeverPAIN or Centor only as decision-support tools in the appropriate context.",
            "Urgently assess features such as airway compromise, severe systemic illness or deep-space infection.",
        ],
        "source_title": "NICE NG84: Sore throat (acute)",
        "source_url": "https://www.nice.org.uk/guidance/ng84/chapter/recommendations",
    },
    {
        "id": "caries-001", "specialty": "Dentistry", "difficulty": "Foundation",
        "answer": "Dental caries", "aliases": ["tooth decay", "dental decay", "caries"],
        "clues": [
            "A 9-year-old reports sensitivity in a molar when eating sweet foods.",
            "The child frequently snacks on foods and drinks containing free sugars.",
            "Examination identifies a plaque-retentive area on the tooth surface.",
            "A localised cavitated lesion is seen in the enamel and dentine.",
            "The lesion is distinct from generalised gingival inflammation.",
            "The mechanism involves plaque bacteria metabolising sugars and producing acids that progressively demineralise tooth structure.",
        ],
        "explanation": "The localised cavitated tooth lesion and sugar/plaque mechanism are consistent with dental caries. Prevention centres on reducing free-sugar exposure, effective plaque control and fluoride.",
        "takeaways": [
            "Dental caries is a biofilm-mediated, sugar-driven disease.",
            "Frequency of free-sugar exposure matters.",
            "Fluoride and effective oral hygiene are important preventive measures.",
        ],
        "source_title": "WHO: Oral health fact sheet",
        "source_url": "https://www.who.int/news-room/fact-sheets/detail/oral-health",
    },
    {
        "id": "gingivitis-001", "specialty": "Dentistry", "difficulty": "Foundation",
        "answer": "Gingivitis", "aliases": ["plaque induced gingivitis", "gingival inflammation"],
        "clues": [
            "A 27-year-old reports that their gums bleed when brushing.",
            "The gums appear erythematous and swollen around several teeth.",
            "Soft plaque is visible along the gingival margin.",
            "Bleeding occurs on gentle probing.",
            "There is no documented evidence in this vignette of periodontal attachment loss.",
            "The pattern is consistent with plaque-associated inflammation of the gingiva.",
        ],
        "explanation": "Erythema, swelling and bleeding associated with plaque are characteristic of gingivitis. It is important to assess periodontal support and distinguish gingivitis from periodontitis.",
        "takeaways": [
            "Bleeding gums are not a normal consequence of brushing.",
            "Plaque control is central to prevention and management.",
            "Assess attachment loss before concluding that disease is confined to the gingiva.",
        ],
        "source_title": "WHO: Oral health fact sheet",
        "source_url": "https://www.who.int/news-room/fact-sheets/detail/oral-health",
    },
    {
        "id": "t2dm-001", "specialty": "Endocrinology", "difficulty": "Intermediate",
        "answer": "Type 2 diabetes mellitus", "aliases": ["type 2 diabetes", "t2dm", "diabetes mellitus type 2"],
        "clues": [
            "A 55-year-old reports increased thirst and passing urine more frequently.",
            "They describe gradual onset over several weeks rather than an abrupt acute illness.",
            "Blood tests show hyperglycaemia.",
            "A laboratory HbA1c result is above the diagnostic threshold used by the local guideline.",
            "The result is interpreted alongside symptoms, repeat testing requirements and possible causes of unreliable HbA1c.",
            "The clinical and laboratory picture is consistent with type 2 diabetes mellitus.",
        ],
        "explanation": "The symptoms and diagnostic-range laboratory findings support diabetes. HbA1c interpretation must account for situations in which it may be unreliable, and diagnosis should follow the applicable guideline.",
        "takeaways": [
            "Polyuria and polydipsia are classic symptoms of hyperglycaemia.",
            "Interpret HbA1c in context; some conditions affect reliability.",
            "Monitoring frequency and treatment targets should be individualised.",
        ],
        "source_title": "NICE NG28: Type 2 diabetes in adults",
        "source_url": "https://www.nice.org.uk/guidance/ng28/chapter/Blood-glucose-management",
    },
]


def normalise_answer(value: str) -> str:
    """Normalise a submitted diagnosis for robust exact alias matching."""
    import re
    text = (value or "").casefold().strip()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def answer_matches(puzzle: dict[str, Any], guess: str) -> bool:
    submitted = normalise_answer(guess)
    accepted = [puzzle.get("answer", ""), *puzzle.get("aliases", [])]
    return bool(submitted) and submitted in {normalise_answer(item) for item in accepted}


def daily_puzzle_index(day_string: str, count: int | None = None) -> int:
    """Stable daily rotation. Optional count makes the helper easy to test."""
    import hashlib
    total = count or len(PUZZLES)
    if total <= 0:
        return 0
    digest = hashlib.sha256(day_string.encode("utf-8")).hexdigest()
    return int(digest[:12], 16) % total


def apply_guess(game: dict[str, Any], puzzle: dict[str, Any], guess: str) -> str:
    """Apply one guess; return empty, correct, incorrect or exhausted."""
    value = (guess or "").strip()[:120]
    if not value:
        return "empty"
    if game.get("finished"):
        return "finished"
    game.setdefault("guesses", []).append(value)
    max_guesses = max(1, min(6, len(puzzle.get("clues", []))))
    game["max_guesses"] = max_guesses
    if answer_matches(puzzle, value):
        game["finished"] = True
        game["solved"] = True
        return "correct"
    if len(game["guesses"]) >= max_guesses:
        game["finished"] = True
        game["solved"] = False
        return "exhausted"
    game["revealed"] = min(len(game["guesses"]) + 1, len(puzzle["clues"]))
    return "incorrect"
