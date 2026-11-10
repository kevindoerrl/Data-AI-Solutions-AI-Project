"""Client voor de ESCO REST API (https://ec.europa.eu/esco/api), met schijfcache.

Gecontroleerd tegen de live API (november 2026):
- GET /search?text=..&type=skill|occupation&language=nl&limit=..&selectedVersion=v1.2.0
    -> resultaten in  _embedded.results[]  met  uri, title, hasReuseLevel[]
- GET /resource/occupation?uri=..&language=nl&selectedVersion=v1.2.0
    -> essentiële skills in  _links.hasEssentialSkill[]  met  uri, title
- Let op: zonder selectedVersion gebruikt de API een OUDERE versie (v1.0.9).

Elk antwoord wordt als JSON-bestand in data/cache/ bewaard. Dezelfde vraag
wordt daarna direct uit de cache beantwoord: snel, en de demo werkt ook als de
verbinding even wegvalt.
"""

import hashlib
import json
from pathlib import Path

import requests

from src.config import CACHE_MAP, ESCO_TAAL, ESCO_VERSIE
from src.models import EscoBeroep, EscoSkill

BASIS_URL = "https://ec.europa.eu/esco/api"


class EscoFout(Exception):
    """De ESCO API is niet bereikbaar en het antwoord staat ook niet in de cache."""


class EscoClient:
    def __init__(self, cache_map: Path = CACHE_MAP, timeout: float = 20, versie: str = ESCO_VERSIE, taal: str = ESCO_TAAL):
        self.cache_map = Path(cache_map)
        self.timeout = timeout
        self.versie = versie
        self.taal = taal
        self.sessie = requests.Session()

    # ---------- intern: ophalen met cache ----------

    def _cache_pad(self, pad: str, params: dict) -> Path:
        sleutel = pad + "?" + json.dumps(params, sort_keys=True, ensure_ascii=False)
        naam = hashlib.sha1(sleutel.encode("utf-8")).hexdigest()
        return self.cache_map / f"{naam}.json"

    def _get(self, pad: str, **params) -> dict:
        params = {**params, "language": self.taal, "selectedVersion": self.versie}
        cache_bestand = self._cache_pad(pad, params)
        if cache_bestand.exists():
            return json.loads(cache_bestand.read_text(encoding="utf-8"))

        try:
            antwoord = self.sessie.get(f"{BASIS_URL}{pad}", params=params, timeout=self.timeout)
            antwoord.raise_for_status()
            data = antwoord.json()
        except (requests.RequestException, ValueError) as e:
            raise EscoFout(f"ESCO API niet bereikbaar ({pad}): {e}") from e

        self.cache_map.mkdir(parents=True, exist_ok=True)
        cache_bestand.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return data

    # ---------- publieke functies ----------

    def zoek_skills(self, tekst: str, limit: int = 8) -> list[EscoSkill]:
        """Zoek ESCO-skills (en kennis) die bij een tekst passen."""
        data = self._get("/search", text=tekst, type="skill", limit=limit)
        resultaten = data.get("_embedded", {}).get("results", [])
        return [
            EscoSkill(
                uri=r["uri"],
                label=r.get("title", ""),
                hergebruik=_laatste_deel((r.get("hasReuseLevel") or [""])[0]),
            )
            for r in resultaten
            if r.get("uri")
        ]

    def zoek_beroepen(self, tekst: str, limit: int = 5) -> list[EscoBeroep]:
        """Zoek ESCO-beroepen bij een functietitel."""
        data = self._get("/search", text=tekst, type="occupation", limit=limit)
        resultaten = data.get("_embedded", {}).get("results", [])
        return [EscoBeroep(uri=r["uri"], label=r.get("title", "")) for r in resultaten if r.get("uri")]

    def haal_beroep(self, uri: str) -> EscoBeroep:
        """Haal één beroep op, inclusief de essentiële skills."""
        data = self._get("/resource/occupation", uri=uri)
        essentieel = data.get("_links", {}).get("hasEssentialSkill", [])
        return EscoBeroep(
            uri=data.get("uri", uri),
            label=data.get("title", ""),
            essentiele_skills=[EscoSkill(uri=s["uri"], label=s.get("title", "")) for s in essentieel if s.get("uri")],
        )


def _laatste_deel(uri: str) -> str:
    """'http://data.europa.eu/esco/skill-reuse-level/transversal' -> 'transversal'"""
    return uri.rstrip("/").rsplit("/", 1)[-1] if uri else ""
