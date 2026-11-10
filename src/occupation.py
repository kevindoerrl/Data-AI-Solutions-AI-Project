"""Stap 4: het best passende ESCO-beroep herkennen.

Bewust ZONDER AI-model, zodat het voorspelbaar is tijdens de demo:
we zoeken op de functietitel en nemen de eerste zoekhit van ESCO.
"""

from src.esco import EscoClient
from src.models import EscoBeroep, EscoSkill, ProfielSkill


def herken_beroep(functietitel: str, esco: EscoClient) -> EscoBeroep | None:
    titel = functietitel.strip()
    if not titel:
        return None
    hits = esco.zoek_beroepen(titel, limit=5)
    if not hits:
        return None
    return esco.haal_beroep(hits[0].uri)


def mogelijk_ontbrekend(beroep: EscoBeroep | None, skills: list[ProfielSkill]) -> list[EscoSkill]:
    """Essentiële skills van het beroep die NIET in het profiel staan (worden niet toegevoegd)."""
    if beroep is None:
        return []
    in_profiel = {s.esco_uri for s in skills}
    return [s for s in beroep.essentiele_skills if s.uri not in in_profiel]
