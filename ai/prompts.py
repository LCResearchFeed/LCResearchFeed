def build_classification_prompt(title: str, abstract: str, source: str, url: str) -> str:
    return f"""
You are a medical researcher specializing in Long COVID.

Classify the paper strictly according to the rules below.

RULES:

1. long_covid = true  
   If symptoms, mechanisms, or effects occur weeks or months after SARS-CoV-2 infection.

2. Choose ONE category (exactly one):
   - Mechanism
   - Treatment
   - Drug
   - Lifestyle
   - Review

3. Choose ONE mechanistic_group (exactly one):
   - Viral Persistence
   - Autoimmunity
   - Dysautonomia
   - Microvascular
   - Mitochondrial
   - Non-mechanistic

4. mechanism = true  
   If the paper describes biological mechanisms.

5. treatment = true  
   If the paper describes interventions or therapies.

6. drug = true  
   If specific drugs are discussed.

7. lifestyle = true  
   If lifestyle interventions are discussed.

8. review = true  
   If the paper is a review article.

CATEGORY LOGIC (strict):
- If review = true → category = "Review"
- Else if lifestyle = true → category = "Lifestyle"
- Else if drug = true → category = "Drug"
- Else if treatment = true → category = "Treatment"
- Else if mechanism = true → category = "Mechanism"
- Else → category = "Mechanism" (default)

MECHANISTIC GROUP LOGIC (strict):
- If mechanism = true → choose one mechanistic_group based on content.
- If mechanism = false → mechanistic_group = "Non-mechanistic"

OUTPUT RULES:
- Return ONLY valid JSON.
- EXACTLY these fields, no more, no less.
- All values must follow the rules above.

JSON FORMAT TO RETURN:

{{
  "score": 0,
  "category": "Mechanism",
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

PAPER:
Title: {title}
Source: {source}
URL: {url}

Abstract:
{abstract}

Respond ONLY with JSON.
""".strip()
