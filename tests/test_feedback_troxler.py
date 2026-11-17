"""Tests naar aanleiding van de feedback van Troxler (november 2026).

1. VCA moet als skill/eis zichtbaar zijn, net als het heftruckcertificaat.
2. Een vaardigheid die bij de eisen staat zonder "pré" (technische tekeningen lezen) is instroom.
3. Gaan meerdere zinnen over dezelfde ESCO-skill, dan vallen er geen zinnen stilletjes weg.
4. Elke regel van de vacature krijgt een uitleg ("achter de schermen").
"""

from src.classify import regel_oordeel
from src.config import VOORBEELD_MAP
from src.llm_providers import kies_provider
from src.models import EscoBeroep, EscoSkill
from src.pipeline import analyseer
from src.uitleg import per_regel

SKILLS = {
    "veilig": EscoSkill(uri="http://data.europa.eu/esco/skill/veilig", label="gezondheids- en veiligheidsnormen toepassen"),
    "tekening": EscoSkill(uri="http://data.europa.eu/esco/skill/tekening", label="technische tekeningen lezen"),
    "pv": EscoSkill(uri="http://data.europa.eu/esco/skill/pv", label="fotovoltaïsche panelen installeren"),
    "app": EscoSkill(uri="http://data.europa.eu/esco/skill/app", label="elektrische en elektronische apparatuur installeren"),
}


class NepEsco:
    """Geeft per zoekterm de skill terug waarvan het label gelijk is aan de zoekterm."""

    def zoek_skills(self, tekst, limit=8):
        return [s for s in SKILLS.values() if s.label == tekst]

    def zoek_beroepen(self, tekst, limit=5):
        return [EscoBeroep(uri="http://data.europa.eu/esco/occupation/monteur", label="monteur elektrische installaties")]

    def haal_beroep(self, uri):
        return EscoBeroep(uri=uri, label="monteur elektrische installaties")


def _elektromonteur():
    tekst = (VOORBEELD_MAP / "elektromonteur.txt").read_text(encoding="utf-8")
    return analyseer(tekst, provider=kies_provider("mock"), esco=NepEsco())


def _per_label(profiel):
    return {s.esco_label: s for s in profiel.skills}


def test_vca_certificaat_wordt_skill_en_is_instroom():
    skill = _per_label(_elektromonteur())["gezondheids- en veiligheidsnormen toepassen"]
    assert "VCA" in skill.bronzin
    assert skill.categorie == "instroom"


def test_technische_tekeningen_bij_de_eisen_is_instroom():
    skill = _per_label(_elektromonteur())["technische tekeningen lezen"]
    assert skill.categorie == "instroom"
    assert skill.regel_advies == "instroom"
    # De taak "volgens tekening" en de eis "je kunt tekeningen lezen" worden samen beoordeeld
    assert any("volgens tekening" in z for z in skill.alle_bronzinnen())


def test_zinnen_over_dezelfde_skill_vallen_niet_weg():
    skill = _per_label(_elektromonteur())["fotovoltaïsche panelen installeren"]
    assert len(skill.alle_bronzinnen()) >= 2


def test_vca_met_eigen_opleiding_is_twijfel_dus_on_the_job():
    advies, reden = regel_oordeel(["VCA-basis is verplicht (of je haalt het in de eerste maand via ons)."])
    assert advies == "on_the_job"
    assert "twijfel" in reden


def test_kopje_eisen_zonder_signaalwoord_is_instroom():
    assert regel_oordeel(["Je kunt technische tekeningen lezen."], rubrieken=["eisen"])[0] == "instroom"


def test_kopje_aanbod_is_on_the_job():
    assert regel_oordeel(["Je leert werken met ons systeem."], rubrieken=["aanbod"])[0] == "on_the_job"


def test_kopje_taken_alleen_geeft_geen_advies():
    assert regel_oordeel(["Je installeert groepenkasten."], rubrieken=["taken"])[0] is None


def test_signaalwoord_gaat_voor_kopje():
    assert regel_oordeel(["Kennis van domotica is een pré."], rubrieken=["eisen"])[0] == "on_the_job"


def test_elke_regel_van_de_vacature_krijgt_uitleg():
    profiel = _elektromonteur()
    regels = per_regel(profiel)
    niet_leeg = [r for r in profiel.schone_tekst.splitlines() if r.strip()]
    assert len(regels) == len(niet_leeg)
    assert all(r.status != "niet_beoordeeld" for r in regels)
    statussen = {r.zin: r.status for r in regels}
    assert statussen["Een bedrijfsbus en goed gereedschap."] == "overgeslagen"
    assert statussen["Ervaring met het installeren van laadpalen is mooi meegenomen."] in ("skill", "geen_esco")
