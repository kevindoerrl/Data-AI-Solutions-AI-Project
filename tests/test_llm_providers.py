"""Tests voor de LLM-laag: mock-provider en JSON-validatie met één herkansing."""

import pytest

from src.config import VOORBEELD_MAP
from src.llm_providers import LLMFout, LLMProvider, MockProvider, kies_provider, vraag_gestructureerd
from src.models import ExtractieResultaat, KoppelResultaat


def test_kies_mock_provider():
    provider = kies_provider("mock")
    assert isinstance(provider, MockProvider)


def test_onbekende_provider_geeft_duidelijke_fout():
    with pytest.raises(LLMFout):
        kies_provider("bestaat-niet")


def test_mock_extractie_vindt_skills_en_signaalwoorden():
    tekst = (VOORBEELD_MAP / "logistiek_medewerker.txt").read_text(encoding="utf-8")
    resultaat = vraag_gestructureerd(
        MockProvider("mock"), "extractie", "", "", ExtractieResultaat,
        context={"tekst": tekst, "signaalwoorden": ["vereist", "pré"]},
    )
    assert resultaat.functietitel == "Logistiek medewerker"
    heftruck = [u for u in resultaat.uitspraken if "heftruckcertificaat" in u.bronzin]
    assert heftruck and heftruck[0].signaalwoorden == ["vereist"]


def test_mock_koppeling_kiest_alleen_uit_kandidaten():
    items = [{
        "nummer": 1, "uitspraak": "heftruck besturen", "bronzin": "",
        "kandidaten": [{"uri": "http://x/1", "label": "heftruck besturen"}, {"uri": "http://x/2", "label": "koken"}],
    }]
    resultaat = vraag_gestructureerd(MockProvider("mock"), "koppeling", "", "", KoppelResultaat, context={"items": items})
    assert resultaat.keuzes[0].esco_uri == "http://x/1"


class _EersteKeerFoutProvider(LLMProvider):
    """Geeft eerst onzin terug, daarna geldige JSON (test de herkansing)."""

    naam = "test"

    def __init__(self):
        super().__init__("test")
        self.aantal = 0

    def genereer(self, taak, systeem, gebruiker, context):
        self.aantal += 1
        if self.aantal == 1:
            return "Dit is geen JSON"
        return '```json\n{"keuzes": [{"nummer": 1, "esco_uri": null}]}\n```'


def test_ongeldige_json_wordt_een_keer_opnieuw_gevraagd():
    provider = _EersteKeerFoutProvider()
    resultaat = vraag_gestructureerd(provider, "koppeling", "", "vraag", KoppelResultaat)
    assert provider.aantal == 2
    assert resultaat.keuzes[0].esco_uri is None


def test_twee_keer_ongeldig_geeft_fout():
    class AltijdFout(LLMProvider):
        def genereer(self, *args):
            return "nee"

    with pytest.raises(LLMFout):
        vraag_gestructureerd(AltijdFout("x"), "koppeling", "", "", KoppelResultaat)
