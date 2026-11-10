"""Het privacyfilter moet e-mail, telefoon en contactpersonen verwijderen."""

from src.config import VOORBEELD_MAP
from src.privacy import verwijder_persoonsgegevens


def _soorten(resultaat):
    return {v.soort for v in resultaat.verwijderd}


def test_email_wordt_verwijderd():
    r = verwijder_persoonsgegevens("Mail naar jan.devries@example.nl voor info.")
    assert "jan.devries@example.nl" not in r.schone_tekst
    assert "e-mailadres" in _soorten(r)


def test_telefoonnummers_worden_verwijderd():
    for nummer in ["010-1234567", "06-12345678", "+31 10 765 4321", "0612345678", "(010) 123 45 67"]:
        r = verwijder_persoonsgegevens(f"Bel ons op {nummer} tijdens kantooruren.")
        assert nummer not in r.schone_tekst, nummer
        assert "telefoonnummer" in _soorten(r), nummer


def test_contactpersoon_wordt_verwijderd():
    r = verwijder_persoonsgegevens("Neem contact op met Jan de Vries via de receptie.")
    assert "Jan de Vries" not in r.schone_tekst
    assert "contact op met [contactpersoon]" in r.schone_tekst
    assert "contactpersoon" in _soorten(r)


def test_contactpersoon_met_hoofdletter_tussenvoegsel():
    r = verwijder_persoonsgegevens("Vragen? Neem contact op met Ahmed El Amrani, teamleider.")
    assert "Ahmed El Amrani" not in r.schone_tekst


def test_gewone_tekst_blijft_staan():
    tekst = "Een geldig heftruckcertificaat is vereist. Je werkt in ploegendienst van 40 uur."
    r = verwijder_persoonsgegevens(tekst)
    assert r.schone_tekst == tekst
    assert r.verwijderd == []


def test_voorbeeldvacatures_bevatten_na_filter_geen_contactgegevens():
    for bestand in VOORBEELD_MAP.glob("*.txt"):
        r = verwijder_persoonsgegevens(bestand.read_text(encoding="utf-8"))
        assert "@" not in r.schone_tekst, bestand.name
        assert {"e-mailadres", "telefoonnummer", "contactpersoon"} <= _soorten(r), bestand.name
