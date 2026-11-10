"""Datastructuren die door de hele pijplijn worden doorgegeven.

Pydantic controleert automatisch of de gegevens het juiste formaat hebben.
Komt er van het AI-model iets terug dat niet klopt, dan geeft Pydantic een fout.
"""

from typing import Literal

from pydantic import BaseModel, Field

Categorie = Literal["instroom", "on_the_job"]
Betrouwbaarheid = Literal["hoog", "midden", "laag"]


# ---------- Stap 1: privacy ----------

class Verwijdering(BaseModel):
    """Eén stukje tekst dat uit de vacature is gehaald vanwege privacy."""

    soort: str  # bijv. "e-mailadres", "telefoonnummer", "contactpersoon"
    waarde: str


class PrivacyResultaat(BaseModel):
    schone_tekst: str
    verwijderd: list[Verwijdering] = Field(default_factory=list)


# ---------- Stap 2: extractie ----------

class SkillUitspraak(BaseModel):
    """Een uitspraak over een skill, zoals het AI-model die uit de vacature haalt."""

    uitspraak: str = Field(description="Korte omschrijving van de skill, bijv. 'heftruck besturen'")
    bronzin: str = Field(description="De zin letterlijk uit de vacature")
    signaalwoorden: list[str] = Field(default_factory=list)


class ExtractieResultaat(BaseModel):
    functietitel: str = ""
    uitspraken: list[SkillUitspraak]


# ---------- Stap 3: ESCO-koppeling ----------

class EscoSkill(BaseModel):
    """Een skill zoals de ESCO API hem teruggeeft. Alleen deze URI's zijn toegestaan."""

    uri: str
    label: str
    # ESCO-hergebruikniveau, bijv. "transversal", "cross-sector", "occupation-specific"
    hergebruik: str = ""


class KoppelKeuze(BaseModel):
    """Keuze van het AI-model per uitspraak: een URI uit de kandidatenlijst, of None."""

    nummer: int  # volgnummer van de uitspraak
    esco_uri: str | None = None


class KoppelResultaat(BaseModel):
    keuzes: list[KoppelKeuze]


# ---------- Stap 4: beroep ----------

class EscoBeroep(BaseModel):
    uri: str
    label: str
    essentiele_skills: list[EscoSkill] = Field(default_factory=list)


# ---------- Stap 5: classificatie ----------

class ClassificatieKeuze(BaseModel):
    nummer: int
    categorie: Categorie
    toelichting: str
    betrouwbaarheid: Betrouwbaarheid


class ClassificatieResultaat(BaseModel):
    keuzes: list[ClassificatieKeuze]


# ---------- Eindresultaat ----------

class ProfielSkill(BaseModel):
    """Eén skill in het eindprofiel."""

    esco_uri: str
    esco_label: str
    uitspraak: str
    bronzin: str
    signaalwoorden: list[str] = Field(default_factory=list)
    categorie: Categorie = "on_the_job"
    toelichting: str = ""
    betrouwbaarheid: Betrouwbaarheid = "laag"
    door_mens_bevestigd: bool = False


class Metadata(BaseModel):
    datum: str
    model: str
    esco_versie: str
    app_versie: str


class Profiel(BaseModel):
    """Het complete skillsprofiel van één vacature."""

    functietitel: str = ""
    beroep: EscoBeroep | None = None
    skills: list[ProfielSkill] = Field(default_factory=list)
    niet_gekoppeld: list[SkillUitspraak] = Field(default_factory=list)
    mogelijk_ontbrekend: list[EscoSkill] = Field(default_factory=list)
    verwijderd: list[Verwijdering] = Field(default_factory=list)
    schone_tekst: str = ""
    metadata: Metadata

    def instroom(self) -> list[ProfielSkill]:
        return [s for s in self.skills if s.categorie == "instroom"]

    def on_the_job(self) -> list[ProfielSkill]:
        return [s for s in self.skills if s.categorie == "on_the_job"]
