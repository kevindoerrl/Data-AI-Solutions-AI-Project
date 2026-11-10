"""Vergelijk de uitvoer van de tool met de handmatig gelabelde referentieset.

Gebruik (vanuit de projectmap):
    python scripts/evaluate.py                       # gebruikt data/precomputed/ (snel, geen API)
    python scripts/evaluate.py --live                # draait de pijplijn opnieuw (LLM_PROVIDER uit .env)
    python scripts/evaluate.py --referentie pad.csv  # andere referentieset

De referentieset is een CSV met kolommen:  vacature_id, esco_uri, categorie
- vacature_id = bestandsnaam van de vacature in data/voorbeelden/ zonder .txt
- categorie   = instroom of on_the_job
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import REFERENTIE_MAP, VOORBEELD_MAP  # noqa: E402
from src.demo import laad_vooraf_berekend  # noqa: E402
from src.evaluatie import bereken, lees_referentieset, rapport  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--referentie", type=Path, default=REFERENTIE_MAP / "referentieset.csv")
    parser.add_argument("--live", action="store_true", help="draai de pijplijn opnieuw i.p.v. vooraf berekende resultaten")
    args = parser.parse_args()

    referentie = lees_referentieset(args.referentie)
    print(f"Referentieset: {args.referentie.name} ({sum(len(v) for v in referentie.values())} regels, {len(referentie)} vacatures)\n")

    tool = {}
    for vacature_id in referentie:
        if args.live:
            from src.pipeline import analyseer

            bestand = VOORBEELD_MAP / f"{vacature_id}.txt"
            if not bestand.exists():
                print(f"! Vacaturetekst {bestand.name} niet gevonden; overgeslagen.")
                continue
            profiel = analyseer(bestand.read_text(encoding="utf-8"))
        else:
            profiel = laad_vooraf_berekend(vacature_id)
            if profiel is None:
                print(f"! Geen vooraf berekend resultaat voor '{vacature_id}'; draai eerst scripts/precompute.py.")
                continue
        print(f"- {vacature_id}: {len(profiel.skills)} skills (model: {profiel.metadata.model})")
        tool[vacature_id] = {s.esco_uri: s.categorie for s in profiel.skills}

    print()
    print(rapport(bereken(tool, referentie)))


if __name__ == "__main__":
    main()
