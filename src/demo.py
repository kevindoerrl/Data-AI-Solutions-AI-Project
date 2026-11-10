"""Demo-modus: vooraf berekende resultaten voor de drie voorbeeldvacatures.

Zonder live API-aanroepen, als terugvaloptie tijdens het symposium.
De bestanden maak je met:  python scripts/precompute.py
"""

import re

from src.config import PRECOMPUTED_MAP, VOORBEELD_MAP
from src.models import Profiel


def _normaliseer(tekst: str) -> str:
    return re.sub(r"\s+", " ", tekst).strip()


def zoek_voorbeeld(tekst: str) -> str | None:
    """Geef de naam van het voorbeeld (bijv. 'elektromonteur') als de tekst daarmee overeenkomt."""
    invoer = _normaliseer(tekst)
    for bestand in VOORBEELD_MAP.glob("*.txt"):
        if _normaliseer(bestand.read_text(encoding="utf-8")) == invoer:
            return bestand.stem
    return None


def laad_vooraf_berekend(naam: str) -> Profiel | None:
    bestand = PRECOMPUTED_MAP / f"{naam}.json"
    if not bestand.exists():
        return None
    return Profiel.model_validate_json(bestand.read_text(encoding="utf-8"))
