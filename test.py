from ai.prompts import build_classification_prompt
from ai.classifier import call_agent

p = {
    "title": "Test title",
    "abstract": "Long covid causes immune dysregulation and persistent viral antigens.",
    "source": "pubmed",
    "url": "https://example.com"
}

prompt = build_classification_prompt(**p)
print(call_agent(prompt))
