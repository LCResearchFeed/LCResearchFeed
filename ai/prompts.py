def build_classification_prompt(title: str, abstract: str, source: str, url: str) -> str:
    return f"""
You are a medical researcher specializing in Long COVID.

Classify the paper strictly according to the rules below.

A paper is Long-COVID relevant if it includes ANY of the following:
- post-infectious biological mechanisms,
- immune dysregulation or autoimmunity,
- viral persistence or viral reservoirs,
- mitochondrial dysfunction,
- neurological or autonomic dysfunction (including dysautonomia or POTS),
- endothelial or microvascular injury,
- chronic inflammation,
- post-viral syndromes similar to Long COVID (ME/CFS),
- organ damage or dysfunction after SARS-CoV-2 infection,
- symptoms or sequelae weeks or months after infection.

Your tasks:
1. Determine whether the paper is Long-COVID relevant (true/false).
2. Assign ONE main category:
   - Mechanism
   - Treatment
   - Drug
   - Lifestyle
   - Review
   - Epidemiology
3. Set the boolean flags:
   - mechanism
   - treatment
   - drug
   - lifestyle
   - review
4. Give a relevance score (0–100).
5. Provide a short 2–4 sentence summary.
6. Provide a short reason explaining your classification.

Return ONLY valid JSON with EXACTLY these fields:

{{
  "score": 0,
  "category": "Mechanism",
  "long_covid": true,
  "mechanism": true,
  "treatment": false,
  "drug": false,
  "lifestyle": false,
  "review": false,
  "summary": "string",
  "reason": "string"
}}

Do NOT add fields.
Do NOT remove fields.
Do NOT rename fields.
Do NOT include any text outside the JSON.

Paper:
Title: {title}
Source: {source}
URL: {url}

Abstract:
{abstract}
""".strip()
