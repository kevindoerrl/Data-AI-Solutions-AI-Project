"""Stap 4: het best passende ESCO-beroep herkennen.

Bewust ZONDER AI-model, zodat het voorspelbaar is tijdens de demo:
1. Bevat de functietitel een woord uit config/beroepen.yaml, dan zoeken we op het
   bijbehorende ESCO-beroep (bijv. "logistiek medewerker" -> "magazijnmedewerker").
2. Staat een beroep met precies die naam in de zoekresultaten, dan nemen we dat;
   anders de eerste zoekhit.
"""

from functools import lru_cache

import yaml

from src.config import CONFIG_MAP
from src.esco import EscoClient
from src.models import EscoBeroep, EscoSkill, ProfielSkill

SYNONIEMEN_BESTAND = CONFIG_MAP / "beroepen.yaml"


@lru_cache(maxsize=1)
def laad_synoniemen() -> dict[str, str]:
    if not SYNONIEMEN_BESTAND.exists():
        return {}
    data = yaml.safe_load(SYNONIEMEN_BESTAND.read_text(encoding="utf-8")) or {}
    return {str(k).lower(): str(v) for k, v in (data.get("synoniemen") or {}).items()}


def zoekterm_voor(functietitel: str) -> str:
    """Vertaal een functietitel naar een ESCO-zoekterm via de synoniemenlijst (langste match wint)."""
    titel = functietitel.lower()
    treffers = [k for k in laad_synoniemen() if k in titel]
    if not treffers:
        return functietitel.strip()
    return laad_synoniemen()[max(treffers, key=len)]


def herken_beroep(functietitel: str, esco: EscoClient) -> EscoBeroep | None:
    titel = functietitel.strip()
    if not titel:
        return None
    zoekterm = zoekterm_voor(titel)
    hits = esco.zoek_beroepen(zoekterm, limit=5)
    if not hits:
        return None
    exact = next((h for h in hits if h.label.lower() == zoekterm.lower()), None)
    return esco.haal_beroep((exact or hits[0]).uri)


def mogelijk_ontbrekend(beroep: EscoBeroep | None, skills: list[ProfielSkill]) -> list[EscoSkill]:
    """Essentiële skills van het beroep die NIET in het profiel staan (worden niet toegevoegd)."""
    if beroep is None:
        return []
    in_profiel = {s.esco_uri for s in skills}
    return [s for s in beroep.essentiele_skills if s.uri not in in_profiel]
