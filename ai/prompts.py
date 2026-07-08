def build_classification_prompt(title: str, abstract: str, source: str, url: str) -> str:
    return f"""
You are a medical researcher specializing in Long COVID.
Your task is to classify the paper strictly according to the rules below and return ONLY valid JSON.

========================================================
LONG COVID RULE
========================================================
long_covid = true  
If the paper describes symptoms, mechanisms, biological findings, or clinical effects occurring weeks or months after SARS‑CoV‑2 infection.

If unclear, infer based on:
- persistent
- post-acute
- post-infectious
- long-term
- months after infection
- PASC
Otherwise: long_covid = false.

========================================================
CATEGORY (choose EXACTLY one)
========================================================
Categories:
- Mechanism
- Treatment
- Drug
- Lifestyle
- Review

Rules:
1. If review = true → category = "Review"
2. Else if lifestyle = true → category = "Lifestyle"
3. Else if drug = true → category = "Drug"
4. Else if treatment = true → category = "Treatment"
5. Else if mechanism = true → category = "Mechanism"
6. Else → category = "Mechanism"

========================================================
MECHANISM FLAG
========================================================
mechanism = true  
If the paper describes biological mechanisms, including:
- immune dysregulation
- autoimmunity
- autoantibodies
- viral persistence
- antigen persistence
- endothelial dysfunction
- microclots
- mitochondrial dysfunction
- metabolic abnormalities
- neuroinflammation
- dysautonomia
- cytokine abnormalities

Otherwise: mechanism = false.

========================================================
TREATMENT FLAG
========================================================
treatment = true  
If the paper describes:
- interventions
- therapies
- rehabilitation
- clinical trials
- RCTs
- monoclonal antibodies
- HBOT
- LDN
- supplements used as treatment

========================================================
DRUG FLAG
========================================================
drug = true  
If specific drugs are discussed.

========================================================
LIFESTYLE FLAG
========================================================
lifestyle = true  
If lifestyle interventions are discussed.

========================================================
REVIEW FLAG
========================================================
review = true  
If the paper is a review.

========================================================
MECHANISTIC GROUP (choose EXACTLY one)
========================================================
If mechanism = true → choose one:
- Viral Persistence
- Autoimmunity
- Dysautonomia
- Microvascular
- Mitochondrial

If mechanism = false → mechanistic_group = "Non-mechanistic".

IMPORTANT:
If mechanistic_group != "Non-mechanistic", mechanism MUST be true.

========================================================
SCORE (0–100)
========================================================
Strong mechanistic evidence → 80–100  
Moderate mechanistic evidence → 70–79  
Weak mechanistic evidence → 60–69  
Treatment / Drug → 60–85  
Lifestyle → 40–60  
Review → 30–50  
Irrelevant → 0–20

Never return 0 unless irrelevant.

========================================================
OUTPUT RULES
========================================================
Return ONLY valid JSON.
No text before or after JSON.
No markdown.
No comments.

========================================================
PAPER
========================================================
Title: {title}
Source: {source}
URL: {url}

Abstract:
{abstract}

Respond ONLY with JSON.
""".strip()
