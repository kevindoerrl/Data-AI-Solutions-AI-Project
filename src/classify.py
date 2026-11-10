"""Stap 5: elke gekoppelde skill indelen als "instroom" of "on_the_job".

Werkwijze:
1. Eenvoudige regels zoeken signaalwoorden uit config/classificatiekader.yaml
   in de bronzin ("vereist" -> instroom, "pré" -> on the job).
2. Het AI-model krijgt het kader, de bronzin en het regeladvies, en kiest.
3. Vangnetten in code (BIJ TWIJFEL ALTIJD ON THE JOB):
   - het model zegt instroom maar de betrouwbaarheid is laag -> on the job
   - het model zegt instroom maar de regels zeggen on the job  -> on the job
   - het model geeft geen antwoord voor een skill               -> on the job
"""

import json
import re
from functools import lru_cache

import yaml

from src.config import KADER_BESTAND
from src.llm_providers import LLMProvider, laad_prompt, vraag_gestructureerd
from src.models import ClassificatieResultaat, ProfielSkill


@lru_cache(maxsize=1)
def laad_kader() -> dict:
    return yaml.safe_load(KADER_BESTAND.read_text(encoding="utf-8"))


def alle_signaalwoorden(kader: dict) -> list[str]:
    woorden = []
    for categorie in kader["categorieen"].values():
        woorden.extend(categorie.get("signaalwoorden", []))
    return woorden


def _bevat(tekst: str, woord: str) -> bool:
    """Komt het woord (of de woordgroep) als los woord voor in de tekst?"""
    return re.search(rf"(?<!\w){re.escape(woord)}(?!\w)", tekst, re.IGNORECASE) is not None


def regel_advies(bronzin: str, signaalwoorden: list[str] | None = None, kader: dict | None = None) -> str | None:
    """Geef "instroom", "on_the_job" of None (geen duidelijk signaal).

    Staan er signalen voor beide in de zin, dan is dat twijfel -> "on_the_job".
    """
    kader = kader or laad_kader()
    tekst = " ".join([bronzin, *(signaalwoorden or [])])
    otj = any(_bevat(tekst, w) for w in kader["categorieen"]["on_the_job"]["signaalwoorden"])
    instroom = any(_bevat(tekst, w) for w in kader["categorieen"]["instroom"]["signaalwoorden"])
    if otj:
        return "on_the_job"
    if instroom:
        return "instroom"
    return None


def kader_als_tekst(kader: dict) -> str:
    regels = []
    for sleutel, categorie in kader["categorieen"].items():
        regels.append(f"{sleutel} ({categorie['uitleg']})")
        for c in categorie["criteria"]:
            regels.append(f"  - {c['naam']}: {c['omschrijving']} Signaal: {c['signaal']}")
    return "\n".join(regels)


def classificeer(skills: list[ProfielSkill], provider: LLMProvider, hergebruik: dict[str, str] | None = None) -> list[ProfielSkill]:
    """Vul categorie, toelichting en betrouwbaarheid in voor elke skill."""
    if not skills:
        return skills
    kader = laad_kader()
    hergebruik = hergebruik or {}

    items = []
    for nummer, s in enumerate(skills, start=1):
        items.append({
            "nummer": nummer,
            "label": s.esco_label,
            "bronzin": s.bronzin,
            "signaalwoorden": s.signaalwoorden,
            "esco_hergebruikniveau": hergebruik.get(s.esco_uri, ""),
            "regel_advies": regel_advies(s.bronzin, s.signaalwoorden, kader),
        })

    systeem = laad_prompt("classificatie", kader=kader_als_tekst(kader))
    gebruiker = "Items:\n" + json.dumps(items, ensure_ascii=False, indent=1)
    resultaat = vraag_gestructureerd(
        provider, "classificatie", systeem, gebruiker, ClassificatieResultaat, context={"items": items}
    )
    keuzes = {k.nummer: k for k in resultaat.keuzes}

    for nummer, (skill, item) in enumerate(zip(skills, items), start=1):
        keuze = keuzes.get(nummer)
        if keuze is None:
            skill.categorie, skill.betrouwbaarheid = "on_the_job", "laag"
            skill.toelichting = "Geen oordeel van het model; bij twijfel on the job."
            continue

        skill.categorie, skill.toelichting, skill.betrouwbaarheid = keuze.categorie, keuze.toelichting, keuze.betrouwbaarheid

        # Vangnetten: bij twijfel altijd on the job
        if skill.categorie == "instroom" and skill.betrouwbaarheid == "laag":
            skill.categorie = "on_the_job"
            skill.toelichting = f"Bij twijfel on the job (lage betrouwbaarheid). {skill.toelichting}"
        elif skill.categorie == "instroom" and item["regel_advies"] == "on_the_job":
            skill.categorie, skill.betrouwbaarheid = "on_the_job", "midden"
            skill.toelichting = f"De vacature noemt dit als iets wat je leert of als pré; daarom on the job. {skill.toelichting}"
    return skills
