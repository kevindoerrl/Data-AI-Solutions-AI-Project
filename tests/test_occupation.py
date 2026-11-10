"""Beroepsherkenning: synoniemenlijst en voorkeur voor een exacte naam."""

from src.models import EscoBeroep
from src.occupation import herken_beroep, zoekterm_voor


def test_synoniem_logistiek_medewerker_wordt_magazijnmedewerker():
    assert zoekterm_voor("Logistiek medewerker") == "magazijnmedewerker"


def test_onbekende_titel_blijft_zoals_hij_is():
    assert zoekterm_voor("Kok") == "Kok"


class NepEsco:
    def zoek_beroepen(self, tekst, limit=5):
        self.zoekterm = tekst
        return [
            EscoBeroep(uri="http://x/ontvangst", label="medewerker grondstoffenontvangst"),
            EscoBeroep(uri="http://x/magazijn", label="magazijnmedewerker"),
        ]

    def haal_beroep(self, uri):
        return EscoBeroep(uri=uri, label=uri.rsplit("/", 1)[-1])


def test_exacte_naam_wint_van_eerste_zoekhit():
    esco = NepEsco()
    beroep = herken_beroep("Logistiek medewerker", esco)
    assert esco.zoekterm == "magazijnmedewerker"
    assert beroep.uri == "http://x/magazijn"
