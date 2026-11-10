"""End-to-end: de volledige pijplijn met LLM_PROVIDER=mock en een nep-ESCO (geen internet nodig)."""

from src.config import VOORBEELD_MAP
from src.llm_providers import kies_provider
from src.models import EscoBeroep, EscoSkill
from src.pipeline import analyseer

ESCO_SKILLS = [
    EscoSkill(uri="http://data.europa.eu/esco/skill/heftruck", label="heftrucks bedienen", hergebruik="cross-sector"),
    EscoSkill(uri="http://data.europa.eu/esco/skill/vca", label="veiligheidscertificaat vca", hergebruik="cross-sector"),
    EscoSkill(uri="http://data.europa.eu/esco/skill/wms", label="warehouse management systeem gebruiken"),
    EscoSkill(uri="http://data.europa.eu/esco/skill/scanner", label="handscanner gebruiken"),
    EscoSkill(uri="http://data.europa.eu/esco/skill/nl", label="Nederlands spreken", hergebruik="transversal"),
]


class NepEsco:
    """Doet alsof het de ESCO API is: geeft altijd dezelfde kandidaten terug."""

    def __init__(self):
        self.zoekvragen = []

    def zoek_skills(self, tekst, limit=8):
        self.zoekvragen.append(tekst)
        return ESCO_SKILLS[:limit]

    def zoek_beroepen(self, tekst, limit=5):
        return [EscoBeroep(uri="http://data.europa.eu/esco/occupation/magazijn", label="magazijnmedewerker")]

    def haal_beroep(self, uri):
        return EscoBeroep(
            uri=uri,
            label="magazijnmedewerker",
            essentiele_skills=[ESCO_SKILLS[0], EscoSkill(uri="http://data.europa.eu/esco/skill/voorraad", label="voorraad bijhouden")],
        )


def _draai():
    tekst = (VOORBEELD_MAP / "logistiek_medewerker.txt").read_text(encoding="utf-8")
    stappen = []
    profiel = analyseer(tekst, provider=kies_provider("mock"), esco=NepEsco(), voortgang=lambda i, b: stappen.append(i))
    return profiel, stappen


def test_pijplijn_draait_end_to_end_met_mock():
    profiel, stappen = _draai()
    assert stappen == [0, 1, 2, 3, 4]
    assert profiel.beroep.label == "magazijnmedewerker"
    assert profiel.skills, "er moeten skills gekoppeld zijn"
    assert profiel.metadata.model == "mock/mock-regels-v1"
    assert profiel.metadata.esco_versie == "v1.2.0"


def test_alleen_esco_uris_in_resultaat():
    profiel, _ = _draai()
    toegestaan = {s.uri for s in ESCO_SKILLS}
    assert all(s.esco_uri in toegestaan for s in profiel.skills)


def test_heftruckcertificaat_is_instroom_en_pre_is_on_the_job():
    profiel, _ = _draai()
    per_label = {s.esco_label: s for s in profiel.skills}
    assert per_label["heftrucks bedienen"].categorie == "instroom"
    assert per_label["warehouse management systeem gebruiken"].categorie == "on_the_job"


def test_persoonsgegevens_niet_in_profiel():
    profiel, _ = _draai()
    assert "Sanne Visser" not in profiel.schone_tekst
    assert all("Sanne" not in s.bronzin for s in profiel.skills)


def test_mogelijk_ontbrekend_bevat_alleen_skills_die_niet_in_profiel_staan():
    profiel, _ = _draai()
    labels = [s.label for s in profiel.mogelijk_ontbrekend]
    assert "voorraad bijhouden" in labels
    assert "heftrucks bedienen" not in labels
