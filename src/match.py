"""Stap 3: elke skill-uitspraak koppelen aan een ESCO-skill.

1. Per uitspraak halen we 8 kandidaten op via de ESCO-zoekfunctie.
2. Het AI-model kiest per uitspraak één kandidaat, of "geen passende ESCO-skill".
3. HARDE REGEL (gecontroleerd in code, niet alleen in de prompt): alleen een URI
   die de ESCO API echt heeft teruggegeven voor DIE uitspraak komt in het
   resultaat. Het label nemen we altijd over uit het ESCO-antwoord, nooit van het model.
"""

import json
import logging

from src.esco import EscoClient
from src.llm_providers import LLMProvider, laad_prompt, vraag_gestructureerd
from src.models import EscoSkill, KoppelKeuze, KoppelResultaat, SkillUitspraak

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


def koppel(
    uitspraken: list[SkillUitspraak], esco: EscoClient, provider: LLMProvider
) -> tuple[list[tuple[SkillUitspraak, EscoSkill]], list[SkillUitspraak]]:
    """Geeft (gekoppelde paren, uitspraken zonder passende ESCO-skill) terug."""
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

    # Komt dezelfde ESCO-skill via meerdere uitspraken binnen, dan houden we er één.
    # We kiezen de uitspraak met de meeste signaalwoorden: "heftruckcertificaat is vereist"
    # zegt meer over instroom dan "je laadt vrachtwagens met een heftruck".
    per_uri: dict[str, tuple[SkillUitspraak, EscoSkill]] = {}
    niet_gekoppeld = []
    for nummer, u in enumerate(uitspraken, start=1):
        skill = geldig.get(nummer)
        if skill is None:
            niet_gekoppeld.append(u)
        elif skill.uri not in per_uri or len(u.signaalwoorden) > len(per_uri[skill.uri][0].signaalwoorden):
            per_uri[skill.uri] = (u, skill)
    return list(per_uri.values()), niet_gekoppeld
