"""Stap 7: het profiel exporteren als CSV en JSON."""

import csv
import io
import json

from src.models import Profiel

CSV_KOLOMMEN = [
    "esco_label",
    "esco_uri",
    "categorie",
    "toelichting",
    "betrouwbaarheid",
    "bronzin",
    "door_mens_bevestigd",
]


def is_definitief(profiel: Profiel) -> bool:
    """Definitief = elke instroomeis is door een mens bevestigd (of omgezet)."""
    return all(s.door_mens_bevestigd for s in profiel.instroom())


def naar_json(profiel: Profiel) -> str:
    data = {
        "metadata": {**profiel.metadata.model_dump(), "definitief": is_definitief(profiel)},
        "functietitel": profiel.functietitel,
        "beroep": {"label": profiel.beroep.label, "uri": profiel.beroep.uri} if profiel.beroep else None,
        "skills": [
            {
                "esco_label": s.esco_label,
                "esco_uri": s.esco_uri,
                "categorie": s.categorie,
                "toelichting": s.toelichting,
                "betrouwbaarheid": s.betrouwbaarheid,
                "bronzin": s.bronzin,
                "door_mens_bevestigd": s.door_mens_bevestigd,
            }
            for s in profiel.skills
        ],
        "mogelijk_ontbrekend": [{"label": s.label, "uri": s.uri} for s in profiel.mogelijk_ontbrekend],
    }
    return json.dumps(data, ensure_ascii=False, indent=2)


def naar_csv(profiel: Profiel) -> str:
    """CSV met ; als scheidingsteken (opent direct goed in Nederlandse Excel).

    Bovenaan staan metadataregels die met # beginnen.
    """
    uitvoer = io.StringIO()
    m = profiel.metadata
    uitvoer.write(f"# datum: {m.datum}\n# model: {m.model}\n# esco_versie: {m.esco_versie}\n")
    uitvoer.write(f"# app_versie: {m.app_versie}\n# definitief: {'ja' if is_definitief(profiel) else 'nee'}\n")
    schrijver = csv.writer(uitvoer, delimiter=";", lineterminator="\n")
    schrijver.writerow(CSV_KOLOMMEN)
    for s in profiel.skills:
        schrijver.writerow([
            s.esco_label, s.esco_uri, s.categorie, s.toelichting, s.betrouwbaarheid, s.bronzin,
            "ja" if s.door_mens_bevestigd else "nee",
        ])
    return uitvoer.getvalue()
