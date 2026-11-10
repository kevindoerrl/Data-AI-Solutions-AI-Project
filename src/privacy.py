"""Stap 1: persoonsgegevens verwijderen VOORDAT er iets naar een AI-model gaat.

We verwijderen:
- e-mailadressen
- telefoonnummers (Nederlandse notaties)
- links naar persoonlijke profielen (LinkedIn e.d.)
- namen van contactpersonen ("Neem contact op met Jan de Vries")

Dit gebeurt met reguliere expressies (zoekpatronen) en een eenvoudige regel
voor namen. Het is niet waterdicht; daarom tonen we in de interface wat er is
verwijderd, zodat een mens kan controleren.
"""

import re

from src.models import PrivacyResultaat, Verwijdering

EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")

# Nederlandse telefoonnummers, bijv. 010-1234567, 06-12345678, +31 10 765 4321, (010) 123 45 67
TELEFOON = re.compile(
    r"(?<![\w+])(?:\+31|0031|\(?0)\)?[\s\-.]?\(?\d{1,3}\)?(?:[\s\-.]?\d){6,8}(?!\d)"
)

# Links naar persoonlijke profielen
PROFIEL_URL = re.compile(
    r"(?:https?://)?(?:www\.)?(?:linkedin\.com/in|facebook\.com|instagram\.com|x\.com|twitter\.com)/[^\s,;)]+",
    re.IGNORECASE,
)

# Een naam: minstens twee woorden met hoofdletter, eventueel met tussenvoegsels (de, van der, ...)
TUSSENVOEGSEL = r"(?:van|de|der|den|ten|ter|te|het|'t|op|in|la|le|da|di|du|del)"
NAAM = rf"[A-Z][a-zà-ÿ'\-]+(?:\s+(?:{TUSSENVOEGSEL}\s+)*[A-Z][a-zà-ÿ'\-]+)+"

# Zinsdelen waarna meestal de naam van een contactpersoon volgt
AANLEIDING = (
    r"(?:contact\s+op\s+met|contactpersoon\s*:?|neem\s+contact\s+met|bel\s+(?:met\s+)?|mail\s+(?:naar\s+)?|"
    r"t\.a\.v\.|ter\s+attentie\s+van|vragen\s*\?\s*|stuur\s+je\s+(?:cv|sollicitatie)\s+naar|"
    r"(?:mevrouw|meneer|mevr\.|dhr\.)\s*)"
)
# (?i:...) = alleen de aanleiding is hoofdletterongevoelig; de naam moet echt met hoofdletters
CONTACTPERSOON = re.compile(rf"(?P<aanleiding>(?i:{AANLEIDING}))\s*(?P<naam>{NAAM})")


def _vervang(patroon: re.Pattern, soort: str, tekst: str, verwijderd: list[Verwijdering]) -> str:
    def weg(m: re.Match) -> str:
        verwijderd.append(Verwijdering(soort=soort, waarde=m.group(0).strip()))
        return f"[{soort}]"

    return patroon.sub(weg, tekst)


def verwijder_persoonsgegevens(tekst: str) -> PrivacyResultaat:
    """Geef de opgeschoonde tekst terug plus een lijst van wat er is weggehaald."""
    verwijderd: list[Verwijdering] = []

    tekst = _vervang(EMAIL, "e-mailadres", tekst, verwijderd)
    tekst = _vervang(PROFIEL_URL, "profiellink", tekst, verwijderd)
    tekst = _vervang(TELEFOON, "telefoonnummer", tekst, verwijderd)

    # Contactpersonen: alleen de naam vervangen, de aanleiding ("contact op met") laten staan.
    def weg_naam(m: re.Match) -> str:
        naam = m.group("naam")
        verwijderd.append(Verwijdering(soort="contactpersoon", waarde=naam))
        return m.group("aanleiding") + " [contactpersoon]"

    tekst = CONTACTPERSOON.sub(weg_naam, tekst)

    # Dezelfde naam kan nog elders in de tekst staan (bijv. in een afsluiting)
    for naam in {v.waarde for v in verwijderd if v.soort == "contactpersoon"}:
        tekst = tekst.replace(naam, "[contactpersoon]")

    return PrivacyResultaat(schone_tekst=tekst, verwijderd=verwijderd)
