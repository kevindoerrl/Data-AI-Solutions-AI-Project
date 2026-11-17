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


def _gevonden(tekst: str, woorden: list[str]) -> list[str]:
    return [w for w in woorden if _bevat(tekst, w)]


def regel_oordeel(
    bronzinnen: list[str],
    signaalwoorden: list[str] | None = None,
    rubrieken: list[str] | None = None,
    kader: dict | None = None,
) -> tuple[str | None, str]:
    """Geef (advies, reden). Advies is "instroom", "on_the_job" of None (geen duidelijk signaal).

    1. Signaalwoorden in de zin(nen) gaan voor. Staan er signalen voor beide in, dan is dat
       twijfel -> "on_the_job".
    2. Geen signaalwoord? Dan beslist het kopje waar de zin onder staat (zie "rubrieken" in
       het kader): "wat bieden wij" -> on the job, "wat vragen wij" -> instroom.
    """
    kader = kader or laad_kader()
    tekst = " ".join([*bronzinnen, *(signaalwoorden or [])])
    otj = _gevonden(tekst, kader["categorieen"]["on_the_job"]["signaalwoorden"])
    instroom = _gevonden(tekst, kader["categorieen"]["instroom"]["signaalwoorden"])
    if otj and instroom:
        return "on_the_job", (
            f'twijfel: zowel een eis ("{instroom[0]}") als een leer-signaal ("{otj[0]}"); bij twijfel on the job'
        )
    if otj:
        return "on_the_job", f'signaalwoord "{otj[0]}"'
    if instroom:
        return "instroom", f'signaalwoord "{instroom[0]}"'

    regels = kader.get("rubrieken", {})
    rubrieken = rubrieken or []
    for rubriek in ("aanbod", "eisen"):  # aanbod eerst: bij twijfel on the job
        if rubriek in rubrieken and rubriek in regels:
            return regels[rubriek]["advies"], regels[rubriek]["uitleg"]
    if "taken" in rubrieken:
        return None, "geen signaalwoord; staat alleen bij de taken"
    return None, "geen signaalwoord gevonden"


def regel_advies(bronzin: str, signaalwoorden: list[str] | None = None, kader: dict | None = None) -> str | None:
    """Kort advies op basis van alleen de signaalwoorden in één zin (zonder kopje)."""
    return regel_oordeel([bronzin], signaalwoorden, None, kader)[0]


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
        rubrieken = [s.rubriek, *s.extra_rubrieken]
        s.regel_advies, s.regel_reden = regel_oordeel(s.alle_bronzinnen(), s.signaalwoorden, rubrieken, kader)
        items.append({
            "nummer": nummer,
            "label": s.esco_label,
            "bronzinnen": s.alle_bronzinnen(),
            "rubriek": s.rubriek,
            "signaalwoorden": s.signaalwoorden,
            "esco_hergebruikniveau": hergebruik.get(s.esco_uri, ""),
            "regel_advies": s.regel_advies,
            "regel_reden": s.regel_reden,
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
            skill.vangnet = "Geen oordeel van het model -> on the job"
            continue

        skill.categorie, skill.toelichting, skill.betrouwbaarheid = keuze.categorie, keuze.toelichting, keuze.betrouwbaarheid
        skill.model_categorie = keuze.categorie

        # Vangnetten: bij twijfel altijd on the job
        if skill.categorie == "instroom" and skill.betrouwbaarheid == "laag":
            skill.categorie = "on_the_job"
            skill.toelichting = f"Bij twijfel on the job (lage betrouwbaarheid). {skill.toelichting}"
            skill.vangnet = "Model zei instroom met lage betrouwbaarheid -> on the job"
        elif skill.categorie == "instroom" and item["regel_advies"] == "on_the_job":
            skill.categorie, skill.betrouwbaarheid = "on_the_job", "midden"
            skill.toelichting = f"De vacature noemt dit als iets wat je leert of als pré; daarom on the job. {skill.toelichting}"
            skill.vangnet = "Model zei instroom, maar de regels vonden een leer-signaal -> on the job"
    return skills
