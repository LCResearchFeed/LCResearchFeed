def build_classification_prompt(title: str, abstract: str, source: str, url: str) -> str:
    return f"""
You are a medical researcher specializing in Long COVID.

Classify the paper.

Rules:
- long_covid = true if symptoms, mechanisms, or effects occur weeks or months after SARS-CoV-2 infection.
- Choose ONE category:
  Mechanism, Treatment, Drug, Lifestyle, Review,
  Treatment, Irrelevant, Epidemiology
- mechanistic_group = ONE of:
  Viral Persistence, Autoimmunity, Dysautonomia, Microvascular, Mitochondrial, Non-mechanistic
- mechanism = true if the paper describes biological mechanisms.
- treatment = true if the paper describes interventions or therapies.
- drug = true if specific drugs are discussed.
- lifestyle = true if lifestyle interventions are discussed.
- review = true if the paper is a review article.
- score = relevance 0–100.
- summary = 2–4 sentences.
- reason = short explanation.

Return ONLY valid JSON with EXACTLY these fields:

{{
  "score": 0,
  "category": "Treatment",
  "long_covid": true,
  "mechanistic_group": "Viral Persistence",
  "mechanism": false,
  "treatment": false,
  "drug": false,
  "lifestyle": false,
  "review": false,
  "summary": "string",
  "reason": "string"
}}

Paper:
Title: {title}
Source: {source}
URL: {url}

Abstract:
{abstract}

Respond ONLY with JSON.
""".strip()
