def build_classification_prompt(title: str, abstract: str, source: str, url: str) -> str:
    return f"""
You classify biomedical papers about Long COVID.
Return ONLY valid JSON. No text outside JSON.

LONG COVID:
true if symptoms/mechanisms/biological findings occur weeks–months after SARS‑CoV‑2 infection.

CATEGORY (one):
CATEGORY LOGIC:
If review=true -> category = Review
Else if lifestyle=true -> category = Lifestyle
Else if drug=true -> category = Drug
Else if treatment=true -> category = Treatment
Else if mechanism=true -> category = Mechanism
Else -> category = Mechanism


FLAGS:
mechanism=true if biological mechanisms: immune dysregulation, autoimmunity, autoantibodies,
viral/antigen persistence, endothelial dysfunction, microclots, mitochondrial dysfunction,
metabolic abnormalities, neuroinflammation, dysautonomia, cytokine abnormalities.

treatment=true if interventions/therapies/clinical trials.
drug=true if specific drugs discussed.
lifestyle=true if lifestyle interventions discussed.
review=true if review/meta-analysis.

MECHANISTIC GROUP (one):
If mechanism=true → choose exactly one of:
Viral Persistence, Autoimmunity, Dysautonomia, Microvascular, Mitochondrial, Neuroinflammation.
Else: Non-mechanistic.

SCORE (0–100):
Strong mechanism: 80–100
Moderate mechanism: 70–79
Weak mechanism: 60–69
Treatment/Drug: 60–85
Lifestyle: 40–60
Review: 30–50
Irrelevant: 0–20

JSON FIELDS:
score, category, long_covid, mechanistic_group, mechanism, treatment, drug, lifestyle, review, summary, reason.

PAPER:
Title: {title}
Source: {source}
URL: {url}

Abstract:
{abstract}

Respond ONLY with JSON.
""".strip()