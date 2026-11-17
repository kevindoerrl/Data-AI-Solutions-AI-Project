# Ontwerplog

Per versie: welk model, welke prompts, welke ESCO-versie, welke aannames en keuzes.

---

## v0.2.0 — Feedback Troxler en "achter de schermen" (17 november 2026)

### Aanleiding
Feedback op v1 (gezien op de live site, die toen met de **mock** draaide, dus zonder AI):
1. Het VCA-certificaat kwam niet in het profiel, het heftruckcertificaat wel.
2. "Technische tekeningen lezen" werd on the job, terwijl de elektromonteur "volgens tekening" werkt en het bij het profiel staat.
3. "Kennis van domotica is een pré" kwam erin, "ervaring met laadpalen is mooi meegenomen" niet.
4. Voor het symposium: duidelijker laten zien wat er achter de schermen gebeurt en op basis van welke aannames zinnen wel of niet gekozen worden.

### Wijzigingen
- **Kopje telt mee (rubriek).** Elke uitspraak krijgt de rubriek van het kopje erboven: taken, eisen, aanbod of overig. Zonder signaalwoord geldt: *eisen* → instroom, *aanbod* → on the job, *taken* → geen advies. Signaalwoorden gaan altijd voor. Instelbaar via `rubrieken` in `config/classificatiekader.yaml`. Lost punt 2 op.
- **Zinnen over dezelfde ESCO-skill vallen niet meer weg.** Voorheen bleef er per ESCO-skill één zin over en verdwenen de rest stilletjes. Nu worden alle zinnen bewaard (`extra_bronzinnen`) en samen beoordeeld (twijfel → on the job). Lost een deel van punt 3 op.
- **Certificaten → onderliggende skill.** De extractieprompt vertaalt een certificaat naar de vaardigheid erachter (VCA → veiligheidsnormen toepassen); de mock kent VCA ook. Nieuwe on-the-job-signalen: "of je haalt het", "in de eerste maand" (logistiek: "VCA-basis is verplicht (of je haalt het in de eerste maand via ons)" = twijfel → on the job). Lost punt 1 op.
- **Elke regel krijgt een verklaring.** De extractie geeft ook `overgeslagen` terug (zin + reden: kopje, bedrijfsinformatie, arbeidsvoorwaarde, sollicitatie). Per uitspraak bewaart de pijplijn de ESCO-kandidaten, de gekozen skill, het regeladvies met reden, het oordeel van het model en welk vangnet eventueel ingreep.
- **Interface: drie tabbladen.** *Skillsprofiel* (met per skill "Hoe is dit besloten?"), *Achter de schermen* (de vacature regel voor regel, met kleur per uitkomst en waarom) en *Aannames van de tool* (de vaste regels en signaalwoorden). Lost punt 4 op.
- **Skills en eisen zonder ESCO-skill** (bijv. diploma Verzorgende IG, BIG-registratie, laadpalen) staan met het regeladvies in een aparte lijst, zodat zichtbaar is dat ze wel in de vacature staan.
- Export: extra kolommen `extra_bronzinnen`, `regel_reden`, `vangnet`.

### Bekende beperking
- ESCO v1.2 heeft geen skill voor laadpalen; met de mock wordt "ervaring met laadpalen" daarom "geen passende ESCO-skill" (nu wel zichtbaar, met uitleg). Een echt AI-model kan mogelijk een ruimere koppeling maken.
- De voorbeeldresultaten in `data/precomputed/` zijn met de mock gemaakt. Draai `python scripts/precompute.py` opnieuw met `LLM_PROVIDER=anthropic` vóór het symposium.

---

## v0.1.0 — MVP (november 2026)

### Configuratie
| Onderdeel | Keuze |
|---|---|
| ESCO | v1.2.0, Nederlandse labels, via de REST API `https://ec.europa.eu/esco/api` |
| LLM (standaard) | Anthropic `claude-opus-5-5`, `effort=low`; server-side fallback bij een weigering |
| LLM (alternatieven) | OpenAI (`gpt-4.1-mini`), Ollama (`llama3.1`), mock (regels, geen AI) |
| Prompts | `config/prompts/extractie.md`, `koppeling.md`, `classificatie.md` |
| Kader | `config/classificatiekader.yaml` |
| Python | 3.12, Streamlit 1.67 |

### ESCO API: gecontroleerd tegen de live API, niet gegokt
- `GET /search?text=…&type=skill|occupation&language=nl&limit=…&selectedVersion=v1.2.0` geeft resultaten in `_embedded.results[]` met `uri`, `title` en `hasReuseLevel`.
- `GET /resource/occupation?uri=…&language=nl&selectedVersion=v1.2.0` geeft de essentiële skills in `_links.hasEssentialSkill[]` (`uri`, `title`).
- **Let op:** zonder `selectedVersion` gebruikt de API standaard **v1.0.9**. De client stuurt de versie daarom altijd mee.
- `offset` bij `/search` is een paginanummer, geen itemnummer.
- Alle antwoorden worden als JSON gecachet in `data/cache/`. Er is geen verloopdatum nodig, omdat de versie vastligt.

### Belangrijkste keuzes
1. **Bij twijfel on the job.** Een onterechte instroomeis sluit werkzoekenden uit. Daarom zijn er drie vangnetten in code (`src/classify.py`):
   - het model zegt instroom maar de betrouwbaarheid is laag → on the job
   - het model zegt instroom maar de regels vinden een on-the-job-signaal ("pré", "wij leiden je op") → on the job
   - er komt geen oordeel van het model → on the job
   Staan er signalen voor beide in één zin, dan telt dat als twijfel → on the job.
2. **Alleen echte ESCO-URI's.** `match.valideer_keuzes` laat alleen een URI door die de ESCO API voor *die* uitspraak heeft teruggegeven. Het label komt altijd uit het ESCO-antwoord, nooit van het model. Dit is getest (`tests/test_match.py`).
3. **Beroepsherkenning zonder LLM.** De eerste ESCO-zoekhit op de functietitel. Dat is voorspelbaar tijdens de demo, maar niet altijd juist (zie beperkingen).
4. **Eén LLM-aanroep per stap** (extractie, koppeling, classificatie), met alle uitspraken tegelijk. Dat is sneller en goedkoper dan één aanroep per skill.
5. **JSON-validatie met Pydantic**; bij ongeldige uitvoer vraagt de code het nog één keer, met de foutmelding erbij.
6. **Dubbele koppelingen.** Komt dezelfde ESCO-skill via meerdere zinnen binnen, dan blijft de zin met de meeste signaalwoorden over. Zo wint "heftruckcertificaat is vereist" van "je laadt vrachtwagens met een heftruck".
7. **Menselijke review.** Een profiel is pas "definitief" als elke instroomeis is bevestigd of omgezet. Daarvoor kan alleen een *concept* worden geëxporteerd. De status staat alleen in de sessie (geen database).
8. **Privacy** met regex plus een heuristiek voor namen na "contact op met", "contactpersoon:", "t.a.v." enzovoort. Dit is niet waterdicht, daarom toont de interface wat er is verwijderd.
9. **CSV met puntkomma** als scheidingsteken, zodat het bestand direct goed opent in Nederlandse Excel. Metadata staat bovenaan in regels die met `#` beginnen.

### Aannames
- De vacature is Nederlandstalig en beroepsgericht (mbo-niveau).
- De voorbeeldvacatures zijn fictief en zelf geschreven, met nep-contactgegevens om het privacyfilter te laten zien.
- "Indicatief < 3 maanden" uit het kader wordt niet berekend; het model weegt het mee via de prompt.

### Bekende beperkingen (gevonden tijdens het bouwen)
- **Beroep "Verzorgende IG"**: de eerste ESCO-hit is *thuiszorgmedewerker*; ESCO heeft geen beroep met precies die naam. *Opgelost met `config/beroepen.yaml`*: dit wordt nu *verpleeghulp*. Laat het team die keuze valideren met de opdrachtgever.
- **Beroep "Logistiek medewerker"**: ESCO *logistiek medewerker* is een **kantoorfunctie**. *Opgelost met `config/beroepen.yaml`*: dit wordt nu *magazijnmedewerker*. Daarbij krijgt een exacte naam in de zoekresultaten voorrang op de eerste hit.
- **De mock-provider** koppelt op woordoverlap, met een kleine trefwoordenlijst voor de pilotberoepen (`_MOCK_TREFWOORDEN` in `src/llm_providers.py`). Voor de drie voorbeelden geeft dat logische koppelingen, maar voor andere vacatures blijft de kwaliteit laag. Diploma's en registraties (Verzorgende IG, BIG) zijn geen ESCO-skills en blijven daarom ongekoppeld, waardoor de verzorgende-vacature in de mock 0 instroomeisen heeft.
- **De demo-resultaten** in `data/precomputed/` zijn met de mock gemaakt. **Voor het symposium opnieuw maken met het echte model** (`scripts/precompute.py --provider anthropic`).
- De ESCO-zoekfunctie werkt op tekst. Lange uitspraken geven minder goede kandidaten dan korte (2 tot 8 woorden); daarom vraagt de extractieprompt om korte uitspraken.
- De referentieset bevat nu 3 voorbeeldregels. De evaluatiecijfers zeggen pas iets als het team een echte, handmatig gelabelde set maakt.

### Vervolgstappen (bewust niet gebouwd in v1)
- Een **keuzemenu met de top 3 ESCO-beroepen**, zodat de gebruiker het beroep kan corrigeren. De synoniemenlijst (`config/beroepen.yaml`) is in v0.1.0 al toegevoegd.
- **Diploma's en certificaten** (Verzorgende IG, VCA, BIG) apart tonen als formele instroomeis, ook als er geen ESCO-skill bij hoort (bijvoorbeeld via ESCO-kwalificaties).
- De ESCO-**transversale skills** en optionele skills (`hasOptionalSkill`) explicieter meewegen in de classificatie (nu krijgt het model alleen het hergebruikniveau mee).
- Bronzin markeren in de vacaturetekst als het model de zin licht anders citeert (fuzzy matching).
- CompetentNL-koppeling, andere talen, kandidaatmatching, accounts en een database vallen buiten de scope van v1.
- Een kleine verzameling **echte** (geanonimiseerde) vacatures per pilotberoep om de prompts op af te stemmen, met `scripts/evaluate.py --live`.
