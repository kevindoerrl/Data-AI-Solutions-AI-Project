"""Rekenwerk van de evaluatie: precisie, recall, overeenstemming en confusion matrix."""

from src.config import REFERENTIE_MAP
from src.evaluatie import bereken, lees_referentieset, rapport


def test_berekening_klopt():
    referentie = {"v1": {"a": "instroom", "b": "on_the_job", "c": "instroom"}}
    tool = {"v1": {"a": "instroom", "b": "instroom", "x": "on_the_job", "y": "on_the_job"}}
    u = bereken(tool, referentie)
    assert u.precisie == 2 / 4      # a en b goed gekoppeld van 4 gevonden
    assert u.recall == 2 / 3        # a en b gevonden van 3 in referentie
    assert u.overeenstemming == 1 / 2  # a gelijk, b verschilt
    assert u.matrix["instroom"]["instroom"] == 1
    assert u.matrix["on_the_job"]["instroom"] == 1
    assert not u.precisie_gehaald


def test_vacatures_buiten_referentie_tellen_niet_mee():
    u = bereken({"v1": {"a": "instroom"}, "v2": {"z": "instroom"}}, {"v1": {"a": "instroom"}})
    assert u.precisie == 1.0
    assert u.precisie_gehaald and u.overeenstemming_gehaald


def test_voorbeeld_referentieset_is_leesbaar_en_rapport_werkt():
    referentie = lees_referentieset(REFERENTIE_MAP / "referentieset.csv")
    assert sum(len(v) for v in referentie.values()) >= 2
    tekst = rapport(bereken({}, referentie))
    assert "Precisie" in tekst and "Confusion matrix" in tekst
