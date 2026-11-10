"""De harde regel: alleen URI's die ESCO zelf heeft voorgesteld mogen in het resultaat."""

from src.match import valideer_keuzes
from src.models import EscoSkill, KoppelKeuze

KANDIDATEN = {
    1: [EscoSkill(uri="http://data.europa.eu/esco/skill/echt-1", label="heftrucks bedienen")],
    2: [EscoSkill(uri="http://data.europa.eu/esco/skill/echt-2", label="in teamverband werken")],
}


def test_verzonnen_uri_wordt_weggegooid():
    keuzes = [KoppelKeuze(nummer=1, esco_uri="http://data.europa.eu/esco/skill/VERZONNEN")]
    geldig, afgekeurd = valideer_keuzes(keuzes, KANDIDATEN)
    assert geldig == {}
    assert afgekeurd == ["http://data.europa.eu/esco/skill/VERZONNEN"]


def test_uri_van_een_ander_item_wordt_weggegooid():
    # echt-2 bestaat wel, maar is niet voorgesteld voor uitspraak 1
    keuzes = [KoppelKeuze(nummer=1, esco_uri="http://data.europa.eu/esco/skill/echt-2")]
    geldig, _ = valideer_keuzes(keuzes, KANDIDATEN)
    assert geldig == {}


def test_geldige_uri_blijft_en_label_komt_uit_esco():
    keuzes = [KoppelKeuze(nummer=1, esco_uri="http://data.europa.eu/esco/skill/echt-1"), KoppelKeuze(nummer=2, esco_uri=None)]
    geldig, afgekeurd = valideer_keuzes(keuzes, KANDIDATEN)
    assert list(geldig) == [1]
    assert geldig[1].label == "heftrucks bedienen"
    assert afgekeurd == []
