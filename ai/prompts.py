def build_classification_prompt(title: str, abstract: str, source: str, url: str) -> str:
    return f"""
You are a biomedical text classifier specialized in Long COVID (PASC).

You will receive a scientific paper title and abstract.

Use ONLY the provided text.
Do NOT hallucinate results.
If unknown, use null/false/"Unknown".

Your output is used in an automated filtering pipeline.

---------------------------------------
TASKS
---------------------------------------

1. Long COVID relevance:
Return true if the paper is primarily about:
Long COVID, PASC, post-COVID syndrome, post-acute sequelae of SARS-CoV-2.

2. Category (ONE only):
Mechanism, Treatment, Drug, Lifestyle, Diagnosis, Rehabilitation, Epidemiology, Review, Other

3. Study type (ONE only):
Randomized Controlled Trial, Clinical Trial, Cohort Study, Case-Control Study,
Cross-Sectional Study, Case Report, Systematic Review, Meta-analysis,
Narrative Review, Basic Science, Animal Study, Cell Study, Modeling Study, Unknown

4. Evidence level:
High, Moderate, Low, Preclinical, Unknown

5. Flags (boolean):
human_study, preclinical, mechanism, treatment, drug, lifestyle, review

6. Confidence (0–100):
How confident classification is based on title + abstract only.

7. Relevance score (0–100):
IMPORTANT: This score is used for ranking in an external system.

Scoring rules (apply mentally, output final number only):
- 0–20: not relevant
- 21–40: weak relevance
- 41–60: moderate relevance
- 61–80: strong relevance
- 81–100: highly relevant clinical or mechanistic LC paper

8. Summary:
2–3 sentences, patient-friendly English.

---------------------------------------
CRITICAL RULES
---------------------------------------
- Return ONLY valid JSON
- Do NOT add extra keys
- Do NOT explain your reasoning in the output
- Use only information from title + abstract

---------------------------------------
OUTPUT FORMAT (MUST MATCH EXACTLY)
---------------------------------------

{
  "score": 0,
  "confidence": 0,

  "long_covid": false,
  "category": "Other",
  "study_type": "Unknown",
  "evidence_level": "Unknown",

  "human_study": false,
  "preclinical": false,
  "mechanism": false,
  "treatment": false,
  "drug": false,
  "lifestyle": false,
  "review": false,

  "summary": "",
  "reason": ""
}

---------------------------------------
PAPER
---------------------------------------

Title:
{title}

Source:
{source}

URL:
{url}

Abstract:
{abstract}
""".strip()