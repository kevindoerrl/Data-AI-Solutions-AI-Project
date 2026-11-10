"""De complete pijplijn: van vacaturetekst naar ESCO-skillsprofiel.

    1. privacy.py     persoonsgegevens verwijderen
    2. extract.py     skill-uitspraken uit de tekst halen (AI)
    3. match.py       koppelen aan ESCO-skills (ESCO-zoekfunctie + AI kiest, code controleert)
    4. occupation.py  ESCO-beroep herkennen (zonder AI) en mogelijk ontbrekende skills
    5. classify.py    instroom of on the job (regels + AI, bij twijfel on the job)

Stap 6 (menselijke review) gebeurt in de interface, stap 7 (export) in export.py.
"""

from datetime import datetime
from typing import Callable

from src.classify import classificeer
from src.config import APP_VERSIE, ESCO_VERSIE
from src.esco import EscoClient
from src.extract import extraheer
from src.llm_providers import LLMProvider, kies_provider
from src.match import koppel
from src.models import Metadata, Profiel, ProfielSkill
from src.occupation import herken_beroep, mogelijk_ontbrekend
from src.privacy import verwijder_persoonsgegevens

# Namen van de stappen, zoals ze in de interface verschijnen
STAPPEN = [
    "Persoonsgegevens verwijderen",
    "Skill-uitspraken uit de vacature halen",
    "Koppelen aan ESCO-skills",
    "ESCO-beroep herkennen",
    "Indelen in instroom en on the job",
]

Voortgang = Callable[[int, str], None]


def _geen_voortgang(stap: int, bericht: str) -> None:
    pass


def analyseer(
    tekst: str,
    provider: LLMProvider | None = None,
    esco: EscoClient | None = None,
    voortgang: Voortgang = _geen_voortgang,
) -> Profiel:
    """Voer alle stappen uit en geef het (nog niet door een mens gecontroleerde) profiel terug."""
    provider = provider or kies_provider()
    esco = esco or EscoClient()

    # 1. Privacy: alles hierna werkt alleen met de opgeschoonde tekst
    voortgang(0, STAPPEN[0])
    privacy = verwijder_persoonsgegevens(tekst)

    # 2. Extractie
    voortgang(1, STAPPEN[1])
    extractie = extraheer(privacy.schone_tekst, provider)

    # 3. Koppeling aan ESCO
    voortgang(2, STAPPEN[2])
    gekoppeld, niet_gekoppeld = koppel(extractie.uitspraken, esco, provider)

    # 4. Beroep
    voortgang(3, STAPPEN[3])
    titel = extractie.functietitel or privacy.schone_tekst.strip().splitlines()[0]
    beroep = herken_beroep(titel, esco)

    # 5. Classificatie
    voortgang(4, STAPPEN[4])
    skills = [
        ProfielSkill(
            esco_uri=skill.uri,
            esco_label=skill.label,
            uitspraak=u.uitspraak,
            bronzin=u.bronzin,
            signaalwoorden=u.signaalwoorden,
        )
        for u, skill in gekoppeld
    ]
    hergebruik = {skill.uri: skill.hergebruik for _, skill in gekoppeld}
    skills = classificeer(skills, provider, hergebruik)

    return Profiel(
        functietitel=extractie.functietitel,
        beroep=beroep,
        skills=skills,
        niet_gekoppeld=niet_gekoppeld,
        mogelijk_ontbrekend=mogelijk_ontbrekend(beroep, skills),
        verwijderd=privacy.verwijderd,
        schone_tekst=privacy.schone_tekst,
        metadata=Metadata(
            datum=datetime.now().isoformat(timespec="seconds"),
            model=provider.omschrijving,
            esco_versie=ESCO_VERSIE,
            app_versie=APP_VERSIE,
        ),
    )
