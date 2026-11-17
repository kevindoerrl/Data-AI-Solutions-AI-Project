"""Stap 3: elke skill-uitspraak koppelen aan een ESCO-skill.

1. Per uitspraak halen we 8 kandidaten op via de ESCO-zoekfunctie.
2. Het AI-model kiest per uitspraak één kandidaat, of "geen passende ESCO-skill".
3. HARDE REGEL (gecontroleerd in code, niet alleen in de prompt): alleen een URI
   die de ESCO API echt heeft teruggegeven voor DIE uitspraak komt in het
   resultaat. Het label nemen we altijd over uit het ESCO-antwoord, nooit van het model.
"""

import json
import logging
from typing import NamedTuple

from src.esco import EscoClient
from src.llm_providers import LLMProvider, laad_prompt, vraag_gestructureerd
from src.models import EscoSkill, KoppelKeuze, KoppelResultaat, SkillUitspraak, UitspraakUitleg

log = logging.getLogger(__name__)

AANTAL_KANDIDATEN = 8


def valideer_keuzes(
    keuzes: list[KoppelKeuze], kandidaten_per_nummer: dict[int, list[EscoSkill]]
) -> tuple[dict[int, EscoSkill], list[str]]:
    """Houd alleen keuzes over waarvan de URI in de kandidatenlijst van dat nummer staat.

    Geeft terug: (geldige koppelingen per nummer, lijst met afgekeurde URI's).
    """
    geldig: dict[int, EscoSkill] = {}
    afgekeurd: list[str] = []
    for keuze in keuzes:
        if keuze.esco_uri is None:
            continue
        kandidaten = {k.uri: k for k in kandidaten_per_nummer.get(keuze.nummer, [])}
        if keuze.esco_uri in kandidaten and keuze.nummer not in geldig:
            geldig[keuze.nummer] = kandidaten[keuze.esco_uri]  # label uit ESCO, niet van het model
        else:
            afgekeurd.append(keuze.esco_uri)
            log.warning("URI afgekeurd (niet door ESCO voorgesteld voor uitspraak %s): %s", keuze.nummer, keuze.esco_uri)
    return geldig, afgekeurd


class Koppeling(NamedTuple):
    """Eén ESCO-skill met de uitspraak die hem het best onderbouwt en eventuele andere uitspraken."""

    hoofd: SkillUitspraak
    skill: EscoSkill
    overige: list[SkillUitspraak]


def koppel(
    uitspraken: list[SkillUitspraak], esco: EscoClient, provider: LLMProvider
) -> tuple[list[Koppeling], list[SkillUitspraak], list[UitspraakUitleg]]:
    """Geeft (koppelingen, uitspraken zonder passende ESCO-skill, uitleg per uitspraak) terug."""
    kandidaten_per_nummer: dict[int, list[EscoSkill]] = {}
    items = []
    for nummer, u in enumerate(uitspraken, start=1):
        kandidaten = esco.zoek_skills(u.uitspraak, limit=AANTAL_KANDIDATEN)
        kandidaten_per_nummer[nummer] = kandidaten
        items.append({
            "nummer": nummer,
            "uitspraak": u.uitspraak,
            "bronzin": u.bronzin,
            "kandidaten": [{"uri": k.uri, "label": k.label} for k in kandidaten],
        })

    # Uitspraken zonder kandidaten hoeven niet naar het model
    met_kandidaten = [i for i in items if i["kandidaten"]]
    keuzes: list[KoppelKeuze] = []
    if met_kandidaten:
        systeem = laad_prompt("koppeling")
        gebruiker = "Items:\n" + json.dumps(met_kandidaten, ensure_ascii=False, indent=1)
        resultaat = vraag_gestructureerd(
            provider, "koppeling", systeem, gebruiker, KoppelResultaat, context={"items": met_kandidaten}
        )
        keuzes = resultaat.keuzes

    geldig, _ = valideer_keuzes(keuzes, kandidaten_per_nummer)

    # Komt dezelfde ESCO-skill via meerdere uitspraken binnen, dan wordt het één skill in het
    # profiel, maar ALLE zinnen blijven bewaard en worden samen beoordeeld. Zo valt
    # "ervaring met laadpalen is mooi meegenomen" niet stilletjes weg naast
    # "je monteert laadpalen". De hoofdzin is die met de meeste signaalwoorden.
    per_uri: dict[str, list[SkillUitspraak]] = {}
    skill_per_uri: dict[str, EscoSkill] = {}
    niet_gekoppeld = []
    uitleg = []
    for nummer, u in enumerate(uitspraken, start=1):
        skill = geldig.get(nummer)
        uitleg.append(UitspraakUitleg(
            uitspraak=u.uitspraak, bronzin=u.bronzin, rubriek=u.rubriek, signaalwoorden=u.signaalwoorden,
            kandidaten=[k.label for k in kandidaten_per_nummer.get(nummer, [])],
            gekozen_label=skill.label if skill else None, gekozen_uri=skill.uri if skill else None,
        ))
        if skill is None:
            niet_gekoppeld.append(u)
        else:
            per_uri.setdefault(skill.uri, []).append(u)
            skill_per_uri[skill.uri] = skill

    koppelingen = []
    for uri, groep in per_uri.items():
        # Hoofdzin: de meeste signaalwoorden; bij gelijkspel een zin uit de eisen, dan de eerste
        hoofd = max(groep, key=lambda u: (len(u.signaalwoorden), u.rubriek == "eisen"))
        koppelingen.append(Koppeling(hoofd, skill_per_uri[uri], [u for u in groep if u is not hoofd]))
        if len(groep) > 1:
            for item in uitleg:
                if item.gekozen_uri == uri:
                    item.samengevoegd = True
    return koppelingen, niet_gekoppeld, uitleg
