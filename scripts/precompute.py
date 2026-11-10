"""Bereken vooraf de resultaten voor de drie voorbeeldvacatures (voor de demo-modus).

Gebruik (vanuit de projectmap):
    python scripts/precompute.py                    # gebruikt LLM_PROVIDER uit .env
    python scripts/precompute.py --provider mock    # zonder API-sleutel

De resultaten komen in data/precomputed/<naam>.json. Draai dit opnieuw na
elke wijziging aan prompts, classificatiekader of model, en vóór het symposium
met het echte model (bijv. anthropic).
"""

import argparse
import sys
from pathlib import Path

# Zorg dat "src" gevonden wordt, ook als je het script vanuit een andere map start
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import PRECOMPUTED_MAP, VOORBEELD_MAP  # noqa: E402
from src.llm_providers import kies_provider  # noqa: E402
from src.pipeline import analyseer  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--provider", help="anthropic | openai | ollama | mock (standaard: uit .env)")
    parser.add_argument("--model", help="modelnaam (standaard: uit .env of de standaard van de provider)")
    args = parser.parse_args()

    provider = kies_provider(args.provider, args.model)
    PRECOMPUTED_MAP.mkdir(parents=True, exist_ok=True)
    print(f"Model: {provider.omschrijving}")

    for bestand in sorted(VOORBEELD_MAP.glob("*.txt")):
        print(f"- {bestand.name} ...", end=" ", flush=True)
        profiel = analyseer(bestand.read_text(encoding="utf-8"), provider=provider)
        doel = PRECOMPUTED_MAP / f"{bestand.stem}.json"
        doel.write_text(profiel.model_dump_json(indent=2), encoding="utf-8")
        print(f"{len(profiel.skills)} skills ({len(profiel.instroom())} instroom) -> {doel.relative_to(PRECOMPUTED_MAP.parent.parent)}")


if __name__ == "__main__":
    main()
