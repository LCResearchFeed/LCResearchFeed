def build_classification_prompt(title: str, abstract: str, source: str, url: str) -> str:
    """
    Long-COVID optimized classification prompt.
    Maximizes detection of LC-relevant mechanisms, even when LC is not explicitly mentioned.
    """

    return f"""
You are a medical researcher specialized in Long COVID.

You will receive the title and abstract of a scientific paper.

Your task is to determine whether this paper is relevant to Long COVID, even if the paper does NOT explicitly mention Long COVID, PASC, or post-acute sequelae.

A paper is considered Long-COVID relevant if it includes ANY of the following:
- post-infectious biological mechanisms,
- immune dysregulation,
- viral persistence,
- mitochondrial dysfunction,
- neurological or autonomic dysfunction,
- endothelial or microvascular injury,
- chronic inflammation,
- post-viral syndromes similar to Long COVID (ME/CFS, dysautonomia, POTS, etc.),
- organ damage or dysfunction following SARS-CoV-2 infection,
- sequelae occurring weeks or months after COVID-19.

Your tasks:

1. Determine whether the paper is Long-COVID relevant (even without explicit LC keywords).
2. Identify the main focus:
   - biological mechanisms / pathophysiology,
   - treatments or potential treatments,
   - drugs or pharmacological interventions,
   - lifestyle or practical interventions,
   - review / overview,
   - epidemiology / prevalence / healthcare utilization.
3. Give a relevance score from 0 to 100 for patients interested in:
   - causes of Long COVID,
   - possible recovery mechanisms,
   - potential treatments or drugs,
   - evidence-based measures they can take.
4. Write a short, patient-friendly summary in English (2–4 sentences).

Return ONLY valid JSON with the following fields:

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

Paper:
Title: {title}
Source: {source}
URL: {url}

Abstract:
{abstract}
""".strip()
