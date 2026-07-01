# ---------------------------------------------------------
# AI Prompt Templates (Style 3)
# ---------------------------------------------------------

def build_classification_prompt(title: str, abstract: str, source: str, url: str) -> str:
    """
    Build the Style-3 AI prompt for llama3.1:8b.
    Uses doubled braces {{ }} so JSON appears literally inside an f-string.
    """

    return f"""
You are a medical researcher specialized in Long COVID.

You will receive the title and abstract of a scientific paper.
Your task is to:

1. Determine whether this paper is primarily about Long COVID or post-acute sequelae of SARS-CoV-2 infection.
2. Identify the main focus of the paper:
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

Return ONLY valid JSON with the following fields.
Use the exact field names and types shown below:

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
