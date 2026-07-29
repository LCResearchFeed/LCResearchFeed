# sources/manual_nature.py
from datetime import datetime

def fetch_manual_nature_papers():
    """
    Voeg hier handmatig Nature papers toe.
    Deze worden volledig meegenomen in de pipeline:
    - AI classificatie
    - deduplicatie
    - seen.json tracking
    - HTML injectie
    """

    papers = [
        {
            "id": "manual-nature-muscle-lc-2026",
            "title": "Skeletal muscle properties in long COVID and ME/CFS differ from those induced by bed rest",
            "abstract": (
                "Patients with long COVID and myalgic encephalomyelitis/chronic fatigue syndrome (ME/CFS) suffer from post-exertional malaise"
                "The accompanying physical inactivity may contribute to a lower aerobic capacity and may explain skeletal muscle adaptations in these patients"
                "Here, we compare whole-body exercise responses and skeletal muscle adaptations after strict 60-day bed rest in healthy people with those"
                " in long COVID and ME/CFS patients, and healthy age- and sex-matched controls. "
            ),
            "url": "https://www.nature.com/articles/s41467-026-75725-y",
            "doi": "10.1038/s41467-026-75725-y",
            "source": "manual",
            "category": "mechanism",
            "date": datetime(2026, 7, 28),
        },

        # Voeg hier meer handmatige papers toe
    ]

    return papers
