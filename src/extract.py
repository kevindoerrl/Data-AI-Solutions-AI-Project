"""Stap 2: het AI-model haalt skill-uitspraken uit de (opgeschoonde) vacaturetekst."""

import re

from src.classify import alle_signaalwoorden, laad_kader
from src.llm_providers import LLMProvider, laad_prompt, vraag_gestructureerd
from src.models import ExtractieResultaat


def _normaliseer(tekst: str) -> str:
    return re.sub(r"\s+", " ", tekst).strip().lower()


def extraheer(tekst: str, provider: LLMProvider) -> ExtractieResultaat:
    kader = laad_kader()
    systeem = laad_prompt("extractie")
    gebruiker = f'Vacaturetekst:\n"""\n{tekst}\n"""'
    resultaat = vraag_gestructureerd(
        provider, "extractie", systeem, gebruiker, ExtractieResultaat,
        context={"tekst": tekst, "signaalwoorden": alle_signaalwoorden(kader)},
    )

    # Opschonen: lege uitspraken weg, dubbele (zelfde uitspraak + bronzin) weg
    gezien, uniek = set(), []
    for u in resultaat.uitspraken:
        sleutel = (_normaliseer(u.uitspraak), _normaliseer(u.bronzin))
        if u.uitspraak.strip() and sleutel not in gezien:
            gezien.add(sleutel)
            uniek.append(u)
    resultaat.uitspraken = uniek
    return resultaat
