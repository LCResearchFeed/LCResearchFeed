# sources/manual.py
from datetime import datetime

def fetch_manual_papers():
    """
    Voeg hier handmatig Springer Nature papers toe.
    Deze worden volledig meegenomen in de pipeline:
    - AI classificatie
    - deduplicatie
    - seen.json tracking
    - HTML injectie
    """

    papers = [
        {
            "id": "manual-wust-hrv-pem-2026",
            "title": "Wearable Heart Rate Variability Monitoring Identifies Autonomic Dysfunction and Thresholds for Post-Exertional Malaise in Long COVID",
            "abstract": (
                "This study investigates the use of wearable HRV monitoring to detect autonomic "
                "dysfunction and identify thresholds for post-exertional malaise (PEM) in Long COVID "
                "patients. The findings suggest HRV-based thresholds may help prevent symptom "
                "exacerbation and guide pacing strategies."
            ),
            "url": "https://link.springer.com/article/10.1007/s40279-026-02487-4",
            "doi": "10.1007/s40279-026-02487-4",
            "source": "manual",
            "category": "mechanism",
            "date": datetime(2026, 7, 25),
        },

        # Voeg hier meer handmatige papers toe
    ]

    return papers
