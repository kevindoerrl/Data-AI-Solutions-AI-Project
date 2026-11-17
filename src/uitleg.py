"""Uitleg "achter de schermen": wat heeft de tool met elke regel van de vacature gedaan?

Per regel van de (opgeschoonde) vacaturetekst bepalen we één status:
- "skill"            er is een ESCO-skill uit gehaald
- "geen_esco"        er staat wel een skill/eis in, maar ESCO heeft er geen passende skill voor
- "overgeslagen"     bewust geen skill (kopje, bedrijfsinformatie, arbeidsvoorwaarde, ...), met reden
- "niet_beoordeeld"  het model heeft niets over deze regel gezegd
"""

import re
from dataclasses import dataclass, field
from typing import Literal

from src.models import Profiel, UitspraakUitleg

Status = Literal["skill", "geen_esco", "overgeslagen", "niet_beoordeeld"]

RUBRIEK_NAMEN = {
    "taken": "taken (wat ga je doen)",
    "eisen": "eisen (wat vragen wij)",
    "aanbod": "aanbod (wat bieden wij)",
    "overig": "overig",
}


@dataclass
class Stap:
    """Eén uitspraak uit een regel, met wat er in elke stap mee gebeurde."""

    uitspraak: str
    esco_label: str | None
    esco_uri: str | None
    kandidaten: list[str]
    samengevoegd: bool
    categorie: str | None  # eindcategorie van de skill in het profiel (na regels, model en vangnet)
    regel_advies: str | None
    regel_reden: str


@dataclass
class RegelUitleg:
    zin: str
    status: Status
    rubriek: str | None = None
    signaalwoorden: list[str] = field(default_factory=list)
    reden: str = ""
    stappen: list[Stap] = field(default_factory=list)


def _norm(tekst: str) -> str:
    tekst = re.sub(r"^[\-•*]\s*", "", tekst.strip())
    return re.sub(r"\s+", " ", tekst).strip().lower()


def per_regel(profiel: Profiel) -> list[RegelUitleg]:
    categorie_per_uri = {s.esco_uri: s.categorie for s in profiel.skills}
    uitleg_per_zin: dict[str, list[UitspraakUitleg]] = {}
    for item in profiel.uitleg:
        uitleg_per_zin.setdefault(_norm(item.bronzin), []).append(item)
    overgeslagen = {_norm(o.zin): o.reden for o in profiel.overgeslagen}

    regels = []
    for ruwe_regel in profiel.schone_tekst.splitlines():
        if not ruwe_regel.strip():
            continue
        zin = re.sub(r"^[\-•*]\s*", "", ruwe_regel.strip())
        sleutel = _norm(zin)
        items = uitleg_per_zin.get(sleutel, [])
        if items:
            stappen = [
                Stap(
                    uitspraak=i.uitspraak, esco_label=i.gekozen_label, esco_uri=i.gekozen_uri,
                    kandidaten=i.kandidaten, samengevoegd=i.samengevoegd,
                    categorie=categorie_per_uri.get(i.gekozen_uri) if i.gekozen_uri else None,
                    regel_advies=i.regel_advies, regel_reden=i.regel_reden,
                )
                for i in items
            ]
            status: Status = "skill" if any(s.esco_uri for s in stappen) else "geen_esco"
            regels.append(RegelUitleg(
                zin=zin, status=status, rubriek=items[0].rubriek,
                signaalwoorden=sorted({w for i in items for w in i.signaalwoorden}), stappen=stappen,
            ))
        elif sleutel in overgeslagen:
            regels.append(RegelUitleg(zin=zin, status="overgeslagen", reden=overgeslagen[sleutel]))
        else:
            regels.append(RegelUitleg(zin=zin, status="niet_beoordeeld", reden="het model heeft deze regel niet genoemd"))
    return regels
