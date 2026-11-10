"""Regelgebaseerde signalen en de vangnetten van de classificatie."""

from src.classify import classificeer, regel_advies
from src.llm_providers import LLMProvider
from src.models import ProfielSkill


def test_vereist_wijst_naar_instroom():
    assert regel_advies("Een geldig heftruckcertificaat is vereist.") == "instroom"


def test_pre_wijst_naar_on_the_job():
    assert regel_advies("Ervaring met een WMS is een pré.") == "on_the_job"


def test_wij_leiden_je_op_wijst_naar_on_the_job():
    assert regel_advies("Wij leiden je op in het werken met de handscanner.") == "on_the_job"


def test_geen_signaal_geeft_geen_advies():
    assert regel_advies("Je zorgt voor een opgeruimde werkplek.") is None


def test_beide_signalen_is_twijfel_dus_on_the_job():
    assert regel_advies("Een rijbewijs is vereist, maar ervaring is een pré.") == "on_the_job"


def test_woord_binnen_ander_woord_telt_niet():
    # "pre" mag niet matchen in "prestaties"
    assert regel_advies("Je levert goede prestaties.") is None


class _VasteProvider(LLMProvider):
    """Geeft altijd hetzelfde antwoord terug (om de vangnetten te testen)."""

    def __init__(self, antwoord: str):
        super().__init__("test")
        self.antwoord = antwoord

    def genereer(self, *args):
        return self.antwoord


def _skill(bronzin: str) -> ProfielSkill:
    return ProfielSkill(esco_uri="http://x/1", esco_label="iets", uitspraak="iets", bronzin=bronzin)


def test_instroom_met_lage_betrouwbaarheid_wordt_on_the_job():
    provider = _VasteProvider('{"keuzes": [{"nummer": 1, "categorie": "instroom", "toelichting": "x", "betrouwbaarheid": "laag"}]}')
    [s] = classificeer([_skill("Je werkt netjes.")], provider)
    assert s.categorie == "on_the_job"


def test_model_zegt_instroom_maar_regel_zegt_pre_wordt_on_the_job():
    provider = _VasteProvider('{"keuzes": [{"nummer": 1, "categorie": "instroom", "toelichting": "x", "betrouwbaarheid": "hoog"}]}')
    [s] = classificeer([_skill("Kennis van domotica is een pré.")], provider)
    assert s.categorie == "on_the_job"


def test_ontbrekend_oordeel_wordt_on_the_job():
    provider = _VasteProvider('{"keuzes": []}')
    [s] = classificeer([_skill("Een diploma is vereist.")], provider)
    assert s.categorie == "on_the_job"
    assert s.betrouwbaarheid == "laag"


def test_duidelijke_instroom_blijft_instroom():
    provider = _VasteProvider('{"keuzes": [{"nummer": 1, "categorie": "instroom", "toelichting": "x", "betrouwbaarheid": "hoog"}]}')
    [s] = classificeer([_skill("Een geldig VCA-certificaat is verplicht.")], provider)
    assert s.categorie == "instroom"
