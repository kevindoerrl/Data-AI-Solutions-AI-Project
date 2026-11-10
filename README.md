# Vacature → ESCO-skillsprofiel (v1)

Een webapplicatie die een Nederlandstalige, beroepsgerichte vacaturetekst omzet in een **skillsprofiel op basis van ESCO v1.2** (Nederlandse labels). Bij elke skill staat of die nodig is **bij instroom** of **on the job** geleerd kan worden.

Dit is een studentenproject van de minor Datadriven & AI Solutions (Hogeschool Rotterdam), groep 3O, in opdracht van Future of Work / Citiverse (Open Urban Platform Rotterdam). De tool wordt als playground demo getoond op het AI Symposium van 11 december 2026.

> **Deze tool gebruikt AI. De uitkomst is een voorstel; een mens beslist. De tool beoordeelt geen kandidaten.**

---

## Hoe werkt het? (in gewone taal)

| Stap | Wat gebeurt er | Bestand | AI? |
|---|---|---|---|
| 1. Privacy | E-mailadressen, telefoonnummers, profiellinks en namen van contactpersonen worden uit de tekst gehaald **voordat** er iets naar een AI-model gaat. De interface laat zien wat er is weggehaald. | `src/privacy.py` | nee |
| 2. Extractie | Het AI-model zoekt alle uitspraken over skills in de vacature, met de letterlijke zin ("bronzin") en signaalwoorden zoals "vereist" of "pré". | `src/extract.py` | ja |
| 3. ESCO-koppeling | Per uitspraak zoekt de tool 8 kandidaat-skills in de ESCO-database. Het AI-model kiest de best passende, of "geen passende ESCO-skill". **De code controleert dat alleen URI's die ESCO zelf heeft teruggegeven in het resultaat komen.** | `src/esco.py`, `src/match.py` | ja |
| 4. Beroep | De functietitel wordt opgezocht in ESCO; de eerste zoekhit is het beroep. Essentiële skills van dat beroep die niet in de vacature staan, worden getoond als "mogelijk ontbrekend" (niet automatisch toegevoegd). | `src/occupation.py` | nee |
| 5. Classificatie | Regels (signaalwoorden uit `config/classificatiekader.yaml`) en het AI-model bepalen samen: instroom of on the job. **Bij twijfel altijd on the job.** | `src/classify.py` | ja |
| 6. Menselijke review | In de interface bevestigt een mens elke instroomeis of zet die om naar on the job. Pas daarna is het profiel "definitief". | `app.py` | nee |
| 7. Export | CSV en JSON met per skill: ESCO-label, ESCO-URI, categorie, toelichting, betrouwbaarheid, bronzin en of een mens het heeft bevestigd. Plus datum, model, ESCO-versie en app-versie. | `src/export.py` | nee |

Zonder code aanpassen kan het team wijzigen:
- **`config/classificatiekader.yaml`**: criteria en signaalwoorden voor instroom en on the job
- **`config/prompts/*.md`**: de instructies voor het AI-model

---

## Installatie (eenmalig)

Nodig: **Python 3.12** (3.11 werkt ook) en **Git**.

```bash
git clone https://github.com/kevindoerrl/Data-AI-Solutions-AI-Project.git
cd Data-AI-Solutions-AI-Project
```

Maak een virtuele omgeving (een aparte "doos" voor de pakketten van dit project) en installeer de pakketten:

**Windows (PowerShell)**
```bash
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

**Mac / Linux**
```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

> Tip: zet de projectmap liever **niet** in OneDrive, Google Drive of iCloud. Die synchroniseren de duizenden kleine bestanden in `.venv`, en dat geeft vertraging en conflicten.

## API-sleutel instellen

1. Kopieer `.env.example` naar een nieuw bestand `.env` (in dezelfde map).
2. Vul in:
   ```
   LLM_PROVIDER=anthropic
   ANTHROPIC_API_KEY=sk-ant-...
   ```
3. Klaar. `.env` staat in `.gitignore` en komt **nooit** op GitHub. Zet een sleutel nooit in code, in een commit of in een chatbericht.

Andere opties voor `LLM_PROVIDER`:
- `mock`: geen AI, vaste regels. Werkt zonder sleutel. Handig om te testen, maar de kwaliteit is laag.
- `openai`: met `OPENAI_API_KEY`.
- `ollama`: een lokaal model via [Ollama](https://ollama.com), zonder sleutel.

Met `LLM_MODEL` kies je een ander model. De standaard voor Anthropic is `claude-opus-5-5`. `LLM_EFFORT=low` houdt het snel, wat prettig is tijdens een live demo.

## Starten

**Windows**
```bash
.venv\Scripts\python.exe -m streamlit run app.py
```

**Mac / Linux**
```bash
.venv/bin/python -m streamlit run app.py
```

De app opent in je browser op http://localhost:8501.

## Demo-modus (terugvaloptie voor het symposium)

Zet in de zijbalk **Demo-modus** aan. Voor de drie voorbeeldvacatures toont de app dan vooraf berekende resultaten uit `data/precomputed/`, zonder live AI- of ESCO-aanroepen.

**Belangrijk:** de huidige bestanden in `data/precomputed/` zijn gemaakt met de **mock** en zijn daarom van lage kwaliteit. Maak ze vóór het symposium opnieuw met het echte model:

```bash
.venv\Scripts\python.exe scripts\precompute.py --provider anthropic
```

Commit daarna de nieuwe bestanden.

## Tests

```bash
.venv\Scripts\python.exe -m pytest
```

De tests hebben geen internet of API-sleutel nodig. Ze gebruiken de mock en nep-ESCO-antwoorden.

## Evaluatie

```bash
.venv\Scripts\python.exe scripts\evaluate.py          # met de vooraf berekende resultaten
.venv\Scripts\python.exe scripts\evaluate.py --live   # pijplijn opnieuw draaien
```

Het script vergelijkt de uitvoer met `data/referentieset/referentieset.csv` (kolommen `vacature_id, esco_uri, categorie`) en rapporteert:
- precisie en recall van de ESCO-koppeling
- de overeenstemming op instroom / on the job
- een confusion matrix

Het laat ook zien of de projectdoelen gehaald zijn (precisie ≥ 0,70 en overeenstemming ≥ 80%). De huidige referentieset bevat maar 3 voorbeeldregels; het team vult die aan met handmatig gelabelde vacatures. `vacature_id` is de bestandsnaam in `data/voorbeelden/` zonder `.txt`.

## Deployen naar Streamlit Community Cloud

1. Zorg dat de code op GitHub staat (deze repo).
2. Ga naar [share.streamlit.io](https://share.streamlit.io), log in met GitHub en kies **Create app**.
3. Kies de repo, branch `main` en het bestand `app.py`. Kies onder **Advanced settings** Python 3.12.
4. Zet bij **Secrets** (TOML-formaat):
   ```toml
   LLM_PROVIDER = "anthropic"
   ANTHROPIC_API_KEY = "sk-ant-..."
   LLM_EFFORT = "low"
   ```
5. Deploy. De app leest de sleutels via `st.secrets`.

## Projectstructuur

```
app.py                         interface (Streamlit)
src/                           pijplijn: privacy, extract, esco, match, occupation, classify, export,
                               llm_providers, models, pipeline, demo, evaluatie, config
config/classificatiekader.yaml criteria en signaalwoorden (aanpasbaar zonder code)
config/prompts/                instructies voor het AI-model
data/voorbeelden/              drie fictieve voorbeeldvacatures
data/precomputed/              vooraf berekende resultaten voor de demo-modus
data/referentieset/            handmatig gelabelde referentieset voor de evaluatie
data/cache/                    cache van ESCO-antwoorden (niet in git)
scripts/precompute.py          maakt de demo-resultaten
scripts/evaluate.py            evaluatie tegen de referentieset
tests/                         pytest
ONTWERPLOG.md                  keuzes, aannames en vervolgstappen per versie
```

## Licentie

[EUPL-1.2](LICENSE), zodat een volgende studentengroep het werk kan hergebruiken en verbeteren.
