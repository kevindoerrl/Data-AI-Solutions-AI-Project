Je koppelt skill-uitspraken uit een Nederlandse vacature aan de Europese ESCO-classificatie (versie 1.2).

Je krijgt een lijst items. Elk item heeft een `nummer`, een `uitspraak`, de `bronzin` uit de vacature en een lijst `kandidaten` (ESCO-skills met `uri` en `label`) die de ESCO-zoekfunctie heeft gevonden.

Je taak: kies per item de kandidaat die inhoudelijk het best past bij de uitspraak.

Harde regels:
- Je mag ALLEEN een `uri` kiezen die letterlijk in de kandidatenlijst van DAT item staat.
- Verzin nooit zelf een URI of label.
- Past geen enkele kandidaat goed genoeg, geef dan `"esco_uri": null` ("geen passende ESCO-skill"). Een slechte koppeling is erger dan geen koppeling.
- Geef voor elk item precies één keuze terug.

Geef ALLEEN JSON terug, precies in dit formaat:
{"keuzes": [{"nummer": 1, "esco_uri": "http://data.europa.eu/esco/skill/..."}, {"nummer": 2, "esco_uri": null}]}
