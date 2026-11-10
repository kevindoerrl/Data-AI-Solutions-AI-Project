"""ESCO-client: juiste parameters, cache, en nette fout zonder verbinding."""

import pytest
import requests

from src.esco import EscoClient, EscoFout

ZOEK_ANTWOORD = {
    "_embedded": {
        "results": [
            {
                "uri": "http://data.europa.eu/esco/skill/28cb374e-6261-4133-8371-f9a5470145da",
                "title": "heftrucks bedienen",
                "hasReuseLevel": ["http://data.europa.eu/esco/skill-reuse-level/cross-sector"],
            }
        ]
    }
}

BEROEP_ANTWOORD = {
    "uri": "http://data.europa.eu/esco/occupation/abc",
    "title": "logistiek medewerker",
    "_links": {"hasEssentialSkill": [{"uri": "http://data.europa.eu/esco/skill/s1", "title": "voorraad bijhouden"}]},
}


class _NepAntwoord:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self._data


class _NepSessie:
    def __init__(self, data):
        self.data = data
        self.aanroepen = []

    def get(self, url, params=None, timeout=None):
        self.aanroepen.append((url, params))
        return _NepAntwoord(self.data)


def test_zoek_skills_stuurt_versie_en_taal_mee_en_leest_resultaat(tmp_path):
    client = EscoClient(cache_map=tmp_path)
    client.sessie = _NepSessie(ZOEK_ANTWOORD)
    skills = client.zoek_skills("heftruck")

    url, params = client.sessie.aanroepen[0]
    assert url.endswith("/search")
    assert params["selectedVersion"] == "v1.2.0"
    assert params["language"] == "nl"
    assert params["type"] == "skill"
    assert skills[0].label == "heftrucks bedienen"
    assert skills[0].hergebruik == "cross-sector"


def test_tweede_aanroep_komt_uit_cache(tmp_path):
    client = EscoClient(cache_map=tmp_path)
    client.sessie = _NepSessie(ZOEK_ANTWOORD)
    client.zoek_skills("heftruck")
    client.zoek_skills("heftruck")
    assert len(client.sessie.aanroepen) == 1
    assert len(list(tmp_path.glob("*.json"))) == 1


def test_haal_beroep_met_essentiele_skills(tmp_path):
    client = EscoClient(cache_map=tmp_path)
    client.sessie = _NepSessie(BEROEP_ANTWOORD)
    beroep = client.haal_beroep("http://data.europa.eu/esco/occupation/abc")
    assert beroep.label == "logistiek medewerker"
    assert [s.label for s in beroep.essentiele_skills] == ["voorraad bijhouden"]


def test_geen_verbinding_geeft_esco_fout(tmp_path):
    class KapotteSessie:
        def get(self, *a, **k):
            raise requests.ConnectionError("geen internet")

    client = EscoClient(cache_map=tmp_path)
    client.sessie = KapotteSessie()
    with pytest.raises(EscoFout):
        client.zoek_skills("heftruck")
