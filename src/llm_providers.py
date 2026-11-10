"""Kleine laag tussen de pijplijn en het AI-model (LLM).

De pijplijn roept altijd `vraag_gestructureerd(...)` aan. Welke provider er
achter zit, bepaal je in .env met LLM_PROVIDER:

    anthropic | openai | ollama | mock

De mock-provider gebruikt geen AI maar eenvoudige regels. Zo werken de app en
de tests zonder API-sleutel, en heb je een terugvaloptie tijdens de demo.
"""

import json
import re

import requests
from pydantic import BaseModel, ValidationError

from src.config import PROMPT_MAP, instelling

STANDAARD_MODELLEN = {
    "anthropic": "claude-opus-5-5",
    "openai": "gpt-4.1-mini",
    "ollama": "llama3.1",
    "mock": "mock-regels-v1",
}

# Modellen waarbij Anthropic bij een weigering automatisch een ander model mag proberen
MODELLEN_MET_FALLBACK = {"claude-opus-5-5", "claude-opus-5", "claude-fable-5-2", "claude-fable-5-1", "claude-sonnet-5-5"}


class LLMFout(Exception):
    """Er ging iets mis bij het AI-model (geen verbinding, ongeldige uitvoer, ...)."""


# ---------------------------------------------------------------------------
# Providers
# ---------------------------------------------------------------------------

class LLMProvider:
    """Basisklasse. Elke provider levert tekst (JSON) terug."""

    naam = "basis"

    def __init__(self, model: str):
        self.model = model

    def genereer(self, taak: str, systeem: str, gebruiker: str, context: dict) -> str:
        raise NotImplementedError

    @property
    def omschrijving(self) -> str:
        return f"{self.naam}/{self.model}"


class AnthropicProvider(LLMProvider):
    naam = "anthropic"

    def __init__(self, model: str):
        super().__init__(model)
        import anthropic  # pas laden als deze provider echt gebruikt wordt

        sleutel = instelling("ANTHROPIC_API_KEY")
        self._anthropic = anthropic
        self._client = anthropic.Anthropic(api_key=sleutel) if sleutel else anthropic.Anthropic()
        self._effort = instelling("LLM_EFFORT", "low")

    def genereer(self, taak, systeem, gebruiker, context):
        extra = {}
        if self.model in MODELLEN_MET_FALLBACK:
            # Bij een (onterechte) weigering probeert Anthropic zelf een ander model
            extra = {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}
        try:
            antwoord = self._client.beta.messages.create(
                model=self.model,
                max_tokens=16000,
                system=systeem,
                messages=[{"role": "user", "content": gebruiker}],
                output_config={"effort": self._effort},
                **extra,
            )
        except self._anthropic.AuthenticationError as e:
            raise LLMFout("Ongeldige of ontbrekende ANTHROPIC_API_KEY.") from e
        except self._anthropic.RateLimitError as e:
            raise LLMFout("Te veel verzoeken naar Anthropic; probeer het zo opnieuw.") from e
        except self._anthropic.APIStatusError as e:
            raise LLMFout(f"Anthropic gaf een fout ({e.status_code}): {e.message}") from e
        except self._anthropic.APIConnectionError as e:
            raise LLMFout("Geen verbinding met Anthropic.") from e

        if antwoord.stop_reason == "refusal":
            raise LLMFout("Het model weigerde deze vraag te beantwoorden.")
        return "".join(blok.text for blok in antwoord.content if blok.type == "text")


class OpenAIProvider(LLMProvider):
    naam = "openai"

    def __init__(self, model: str):
        super().__init__(model)
        import openai

        self._openai = openai
        self._client = openai.OpenAI(api_key=instelling("OPENAI_API_KEY") or None)

    def genereer(self, taak, systeem, gebruiker, context):
        try:
            antwoord = self._client.chat.completions.create(
                model=self.model,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": systeem},
                    {"role": "user", "content": gebruiker},
                ],
            )
        except self._openai.OpenAIError as e:
            raise LLMFout(f"OpenAI gaf een fout: {e}") from e
        return antwoord.choices[0].message.content or ""


class OllamaProvider(LLMProvider):
    """Lokaal model via Ollama (https://ollama.com). Geen API-sleutel nodig."""

    naam = "ollama"

    def __init__(self, model: str):
        super().__init__(model)
        self._url = instelling("OLLAMA_URL", "http://localhost:11434").rstrip("/")

    def genereer(self, taak, systeem, gebruiker, context):
        try:
            r = requests.post(
                f"{self._url}/api/chat",
                json={
                    "model": self.model,
                    "format": "json",
                    "stream": False,
                    "messages": [
                        {"role": "system", "content": systeem},
                        {"role": "user", "content": gebruiker},
                    ],
                },
                timeout=300,
            )
            r.raise_for_status()
        except requests.RequestException as e:
            raise LLMFout(f"Ollama niet bereikbaar op {self._url}: {e}") from e
        return r.json()["message"]["content"]


class MockProvider(LLMProvider):
    """Geen AI: eenvoudige, voorspelbare regels die realistische uitvoer geven.

    De pijplijn geeft via `context` dezelfde gegevens mee die ook in de prompt
    staan, zodat de mock niet de prompttekst hoeft te ontleden.
    """

    naam = "mock"

    def genereer(self, taak, systeem, gebruiker, context):
        if taak == "extractie":
            return json.dumps(_mock_extractie(context["tekst"], context.get("signaalwoorden", [])))
        if taak == "koppeling":
            return json.dumps(_mock_koppeling(context["items"]))
        if taak == "classificatie":
            return json.dumps(_mock_classificatie(context["items"]))
        raise LLMFout(f"Mock kent taak '{taak}' niet.")


# --- hulpfuncties voor de mock ---

_KOPJES_ZONDER_SKILLS = ("over ons", "wie zijn wij", "over het bedrijf", "interesse", "solliciteren", "contact")


def _mock_extractie(tekst: str, signaalwoorden: list[str]) -> dict:
    """Neem elke opsommingsregel ('- ...') als skill-uitspraak."""
    regels = [r.strip() for r in tekst.splitlines()]
    titel = next((r for r in regels if r), "")
    titel = re.split(r"[–\-(]", titel)[0].strip()

    uitspraken = []
    for regel in regels:
        if not regel.startswith(("-", "•", "*")):
            continue
        zin = regel.lstrip("-•* ").strip()
        if not zin:
            continue
        gevonden = [w for w in signaalwoorden if re.search(rf"(?<!\w){re.escape(w)}(?!\w)", zin, re.IGNORECASE)]
        uitspraken.append({"uitspraak": _kern(zin), "bronzin": zin, "signaalwoorden": gevonden})
    return {"functietitel": titel, "uitspraken": uitspraken}


def _kern(zin: str) -> str:
    """Maak een korte omschrijving van een zin (eerste deel, zonder aanloop)."""
    kort = re.split(r"[,.;(]", zin)[0]
    kort = re.sub(r"^(je|jij|wij|we)\s+(bent|hebt|kunt|werkt|leiden je op in|beschikt over)\s+", "", kort, flags=re.IGNORECASE)
    return kort.strip()[:80]


def _woorden(tekst: str) -> set[str]:
    return {w for w in re.findall(r"\w+", tekst.lower()) if len(w) > 3}


def _mock_koppeling(items: list[dict]) -> dict:
    """Kies per uitspraak de kandidaat met de meeste overlappende woorden."""
    keuzes = []
    for item in items:
        bron = _woorden(item["uitspraak"] + " " + item.get("bronzin", ""))
        beste, beste_score = None, 0
        for kandidaat in item["kandidaten"]:
            score = len(bron & _woorden(kandidaat["label"]))
            if score > beste_score:
                beste, beste_score = kandidaat["uri"], score
        keuzes.append({"nummer": item["nummer"], "esco_uri": beste})
    return {"keuzes": keuzes}


def _mock_classificatie(items: list[dict]) -> dict:
    """Volg het regeladvies; zonder duidelijk signaal: on the job (bij twijfel)."""
    keuzes = []
    for item in items:
        advies = item.get("regel_advies")
        if advies == "instroom":
            keuzes.append({
                "nummer": item["nummer"], "categorie": "instroom", "betrouwbaarheid": "midden",
                "toelichting": "De vacature noemt dit als harde eis (signaalwoord in de bronzin).",
            })
        elif advies == "on_the_job":
            keuzes.append({
                "nummer": item["nummer"], "categorie": "on_the_job", "betrouwbaarheid": "midden",
                "toelichting": "De vacature geeft aan dat dit geleerd kan worden of een pré is.",
            })
        else:
            keuzes.append({
                "nummer": item["nummer"], "categorie": "on_the_job", "betrouwbaarheid": "laag",
                "toelichting": "Geen duidelijk signaal gevonden; bij twijfel on the job.",
            })
    return {"keuzes": keuzes}


# ---------------------------------------------------------------------------
# Provider kiezen en gestructureerd vragen
# ---------------------------------------------------------------------------

PROVIDERS = {
    "anthropic": AnthropicProvider,
    "openai": OpenAIProvider,
    "ollama": OllamaProvider,
    "mock": MockProvider,
}


def kies_provider(naam: str | None = None, model: str | None = None) -> LLMProvider:
    """Maak de provider aan die in .env (of via de parameters) is ingesteld."""
    naam = (naam or instelling("LLM_PROVIDER", "mock")).strip().lower()
    if naam not in PROVIDERS:
        raise LLMFout(f"Onbekende LLM_PROVIDER '{naam}'. Kies uit: {', '.join(PROVIDERS)}.")
    model = model or instelling("LLM_MODEL") or STANDAARD_MODELLEN[naam]
    return PROVIDERS[naam](model)


def laad_prompt(naam: str, **vervangingen: str) -> str:
    """Lees config/prompts/<naam>.md en vul {{plaatshouders}} in."""
    tekst = (PROMPT_MAP / f"{naam}.md").read_text(encoding="utf-8")
    for sleutel, waarde in vervangingen.items():
        tekst = tekst.replace("{{" + sleutel + "}}", waarde)
    return tekst


def _haal_json_uit(tekst: str) -> str:
    """Modellen zetten JSON soms tussen ```-tekens of met tekst eromheen. Pak het JSON-deel."""
    tekst = tekst.strip()
    blok = re.search(r"```(?:json)?\s*(.*?)```", tekst, re.DOTALL)
    if blok:
        tekst = blok.group(1).strip()
    begin, eind = tekst.find("{"), tekst.rfind("}")
    if begin != -1 and eind > begin:
        tekst = tekst[begin : eind + 1]
    return tekst


def vraag_gestructureerd(
    provider: LLMProvider,
    taak: str,
    systeem: str,
    gebruiker: str,
    schema: type[BaseModel],
    context: dict | None = None,
):
    """Vraag het model om JSON en controleer die met een Pydantic-schema.

    Is de uitvoer ongeldig, dan proberen we het nog één keer, met de foutmelding erbij.
    """
    context = context or {}
    fout = None
    for poging in range(2):
        vraag = gebruiker
        if fout:
            vraag += (
                "\n\nJe vorige antwoord was geen geldige JSON volgens het gevraagde formaat. "
                f"Foutmelding: {fout}\nGeef nu alleen geldige JSON terug."
            )
        ruw = provider.genereer(taak, systeem, vraag, context)
        try:
            return schema.model_validate_json(_haal_json_uit(ruw))
        except ValidationError as e:
            fout = str(e)[:1000]
    raise LLMFout(f"Het model gaf twee keer ongeldige uitvoer voor taak '{taak}'.")
