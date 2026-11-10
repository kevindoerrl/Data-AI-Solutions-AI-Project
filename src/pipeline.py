"""De complete pijplijn: van vacaturetekst naar ESCO-skillsprofiel.

Stap (a): de pijplijn geeft nog een vast dummyprofiel terug, zodat de interface
gebouwd en getest kan worden. In de volgende stappen worden de echte modules
(privacy, extract, esco, match, occupation, classify) hier aangesloten.
"""

from datetime import datetime
from typing import Callable

from src.config import APP_VERSIE, ESCO_VERSIE
from src.llm_providers import LLMProvider, kies_provider
from src.models import EscoBeroep, EscoSkill, Metadata, Profiel, ProfielSkill, Verwijdering

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


def analyseer(tekst: str, provider: LLMProvider | None = None, voortgang: Voortgang = _geen_voortgang) -> Profiel:
    """Voer de pijplijn uit. (Nu nog: dummyresultaat.)"""
    provider = provider or kies_provider()
    for i, naam in enumerate(STAPPEN):
        voortgang(i, naam)
    return dummy_profiel(provider.omschrijving)


def dummy_profiel(model: str = "mock/mock-regels-v1") -> Profiel:
    """Vast voorbeeldprofiel voor het bouwen van de interface (geen echte ESCO-data)."""
    return Profiel(
        functietitel="Logistiek medewerker (dummy)",
        beroep=EscoBeroep(uri="http://data.europa.eu/esco/occupation/DUMMY", label="magazijnmedewerker (dummy)"),
        skills=[
            ProfielSkill(
                esco_uri="http://data.europa.eu/esco/skill/DUMMY-1",
                esco_label="heftruck besturen (dummy)",
                uitspraak="heftruckcertificaat",
                bronzin="Een geldig heftruckcertificaat is vereist.",
                signaalwoorden=["vereist"],
                categorie="instroom",
                toelichting="De vacature noemt dit als harde eis.",
                betrouwbaarheid="hoog",
            ),
            ProfielSkill(
                esco_uri="http://data.europa.eu/esco/skill/DUMMY-2",
                esco_label="magazijnbeheersystemen gebruiken (dummy)",
                uitspraak="warehouse management systeem",
                bronzin="Ervaring met een warehouse management systeem is een pré.",
                signaalwoorden=["pré"],
                categorie="on_the_job",
                toelichting="Genoemd als pré; wordt tijdens het inwerken aangeleerd.",
                betrouwbaarheid="midden",
            ),
        ],
        mogelijk_ontbrekend=[EscoSkill(uri="http://data.europa.eu/esco/skill/DUMMY-3", label="voorraad controleren (dummy)")],
        verwijderd=[Verwijdering(soort="e-mailadres", waarde="s.visser@transhaven-voorbeeld.nl")],
        schone_tekst="Een geldig heftruckcertificaat is vereist.\nErvaring met een warehouse management systeem is een pré.",
        metadata=Metadata(
            datum=datetime.now().isoformat(timespec="seconds"),
            model=model,
            esco_versie=ESCO_VERSIE,
            app_versie=APP_VERSIE,
        ),
    )
