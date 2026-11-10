"""Export moet geldige CSV en JSON opleveren."""

import csv
import io
import json

from src.export import CSV_KOLOMMEN, is_definitief, naar_csv, naar_json
from src.models import Metadata, Profiel, ProfielSkill


def _profiel() -> Profiel:
    return Profiel(
        functietitel="Test",
        skills=[
            ProfielSkill(esco_uri="http://x/1", esco_label="heftrucks bedienen", uitspraak="heftruck",
                         bronzin='Een "geldig" certificaat; vereist.', categorie="instroom",
                         toelichting="Harde eis.", betrouwbaarheid="hoog"),
            ProfielSkill(esco_uri="http://x/2", esco_label="in teamverband werken", uitspraak="team",
                         bronzin="Samenwerken.", categorie="on_the_job", toelichting="Leer je.", betrouwbaarheid="midden"),
        ],
        metadata=Metadata(datum="2026-11-10T12:00:00", model="mock/test", esco_versie="v1.2.0", app_versie="0.1.0"),
    )


def test_json_is_geldig_en_compleet():
    data = json.loads(naar_json(_profiel()))
    assert data["metadata"]["esco_versie"] == "v1.2.0"
    assert data["metadata"]["definitief"] is False
    assert data["skills"][0]["esco_uri"] == "http://x/1"
    assert set(data["skills"][0]) == set(CSV_KOLOMMEN)


def test_csv_is_geldig_en_bevat_alle_kolommen():
    tekst = naar_csv(_profiel())
    regels = [r for r in tekst.splitlines() if not r.startswith("#")]
    rijen = list(csv.DictReader(io.StringIO("\n".join(regels)), delimiter=";"))
    assert list(rijen[0]) == CSV_KOLOMMEN
    assert len(rijen) == 2
    assert rijen[0]["bronzin"] == 'Een "geldig" certificaat; vereist.'  # aanhalingstekens en ; blijven heel
    assert rijen[0]["door_mens_bevestigd"] == "nee"
    assert "# model: mock/test" in tekst


def test_definitief_pas_na_bevestiging_van_alle_instroomeisen():
    profiel = _profiel()
    assert not is_definitief(profiel)
    profiel.skills[0].door_mens_bevestigd = True
    assert is_definitief(profiel)
