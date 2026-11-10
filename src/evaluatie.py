"""Rekenwerk voor de evaluatie: tool-uitvoer vergelijken met een handmatig gelabelde referentieset.

Begrippen in gewone taal:
- precisie:  van alle ESCO-skills die de tool vond, welk deel staat ook in de referentieset?
             (hoog = de tool verzint weinig onzin)
- recall:    van alle skills in de referentieset, welk deel heeft de tool gevonden?
             (hoog = de tool mist weinig)
- overeenstemming: bij skills die zowel de tool als de referentie hebben, hoe vaak
             is instroom / on the job hetzelfde?
- confusion matrix: tabel van referentie (rijen) tegen tool (kolommen).
"""

import csv
from dataclasses import dataclass, field
from pathlib import Path

CATEGORIEEN = ["instroom", "on_the_job"]
DOEL_PRECISIE = 0.70
DOEL_OVEREENSTEMMING = 0.80

# Per vacature: {esco_uri: categorie}
Labels = dict[str, dict[str, str]]


@dataclass
class Uitslag:
    precisie: float
    recall: float
    overeenstemming: float
    aantal_tool: int
    aantal_referentie: int
    aantal_overlap: int
    # matrix[referentie][tool] = aantal
    matrix: dict[str, dict[str, int]] = field(default_factory=dict)

    @property
    def precisie_gehaald(self) -> bool:
        return self.precisie >= DOEL_PRECISIE

    @property
    def overeenstemming_gehaald(self) -> bool:
        return self.overeenstemming >= DOEL_OVEREENSTEMMING


def lees_referentieset(pad: Path) -> Labels:
    labels: Labels = {}
    with open(pad, encoding="utf-8-sig", newline="") as f:
        for rij in csv.DictReader(f):
            if not rij.get("vacature_id") or not rij.get("esco_uri"):
                continue
            categorie = rij["categorie"].strip().lower().replace(" ", "_")
            labels.setdefault(rij["vacature_id"].strip(), {})[rij["esco_uri"].strip()] = categorie
    return labels


def bereken(tool: Labels, referentie: Labels) -> Uitslag:
    """Vergelijk alleen vacatures die in de referentieset staan."""
    matrix = {r: {t: 0 for t in CATEGORIEEN} for r in CATEGORIEEN}
    n_tool = n_ref = n_overlap = n_gelijk = 0

    for vacature_id, ref_labels in referentie.items():
        tool_labels = tool.get(vacature_id, {})
        n_tool += len(tool_labels)
        n_ref += len(ref_labels)
        for uri in tool_labels.keys() & ref_labels.keys():
            n_overlap += 1
            r, t = ref_labels[uri], tool_labels[uri]
            if r in matrix and t in matrix[r]:
                matrix[r][t] += 1
            n_gelijk += r == t

    return Uitslag(
        precisie=n_overlap / n_tool if n_tool else 0.0,
        recall=n_overlap / n_ref if n_ref else 0.0,
        overeenstemming=n_gelijk / n_overlap if n_overlap else 0.0,
        aantal_tool=n_tool,
        aantal_referentie=n_ref,
        aantal_overlap=n_overlap,
        matrix=matrix,
    )


def rapport(uitslag: Uitslag) -> str:
    def vink(ok: bool) -> str:
        return "GEHAALD" if ok else "NIET GEHAALD"

    regels = [
        "Evaluatie ESCO-skillsprofiel",
        "=" * 40,
        f"Skills gevonden door de tool:   {uitslag.aantal_tool}",
        f"Skills in de referentieset:     {uitslag.aantal_referentie}",
        f"Overlap (zelfde ESCO-URI):      {uitslag.aantal_overlap}",
        "",
        f"Precisie ESCO-koppeling:  {uitslag.precisie:.2f}   (doel >= {DOEL_PRECISIE:.2f})  {vink(uitslag.precisie_gehaald)}",
        f"Recall ESCO-koppeling:    {uitslag.recall:.2f}",
        f"Overeenstemming instroom/on the job: {uitslag.overeenstemming:.0%}   "
        f"(doel >= {DOEL_OVEREENSTEMMING:.0%})  {vink(uitslag.overeenstemming_gehaald)}",
        "",
        "Confusion matrix (rijen = referentie, kolommen = tool):",
        f"{'':>14}{'instroom':>12}{'on_the_job':>12}",
    ]
    for r in CATEGORIEEN:
        regels.append(f"{r:>14}{uitslag.matrix[r]['instroom']:>12}{uitslag.matrix[r]['on_the_job']:>12}")
    return "\n".join(regels)
