"""Centrale instellingen: paden, versies en waarden uit .env of st.secrets."""

import os
from pathlib import Path

from dotenv import load_dotenv

# Map van het project (de map waar app.py staat)
PROJECT_MAP = Path(__file__).resolve().parent.parent

CONFIG_MAP = PROJECT_MAP / "config"
PROMPT_MAP = CONFIG_MAP / "prompts"
DATA_MAP = PROJECT_MAP / "data"
VOORBEELD_MAP = DATA_MAP / "voorbeelden"
PRECOMPUTED_MAP = DATA_MAP / "precomputed"
REFERENTIE_MAP = DATA_MAP / "referentieset"
CACHE_MAP = DATA_MAP / "cache"
KADER_BESTAND = CONFIG_MAP / "classificatiekader.yaml"

# Versies (komen ook in de export terecht)
APP_VERSIE = "0.1.0"
ESCO_VERSIE = "v1.2.0"
ESCO_TAAL = "nl"

# .env inlezen (bestaat het bestand niet, dan gebeurt er niets)
load_dotenv(PROJECT_MAP / ".env")


def instelling(naam: str, standaard: str = "") -> str:
    """Lees een instelling uit de omgeving (.env) of, op Streamlit Cloud, uit st.secrets."""
    waarde = os.getenv(naam)
    if waarde:
        return waarde
    try:
        import streamlit as st

        if naam in st.secrets:
            return str(st.secrets[naam])
    except Exception:
        # Geen Streamlit of geen secrets.toml: dat is prima
        pass
    return standaard
