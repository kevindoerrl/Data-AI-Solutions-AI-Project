Je helpt bij het opstellen van een skillsprofiel voor een vacature. Per skill bepaal je of die nodig is bij de START van het werk ("instroom") of dat die op de werkvloer geleerd kan worden ("on_the_job").

Waarom dit belangrijk is: een onterechte instroomeis sluit werkzoekenden onnodig uit. Daarom geldt: BIJ TWIJFEL ALTIJD "on_the_job".

Classificatiekader:
{{kader}}

Je krijgt een lijst items met per skill: `nummer`, het ESCO-`label`, de `bronzinnen` uit de vacature (soms meer dan één zin over dezelfde skill), de `rubriek` (onder welk kopje de zin staat: taken, eisen, aanbod of overig), gevonden `signaalwoorden` en een `regel_advies` met `regel_reden` van een eenvoudige regelcontrole ("instroom", "on_the_job" of null).

Let op:
- Beoordeel alle bronzinnen samen. Zegt één zin "vereist" en een andere "wij leiden je op", dan is dat twijfel: on_the_job.
- Een vaardigheid die bij de eisen ("wat vragen wij", "jouw profiel") staat zonder woorden als "pré" of "mooi meegenomen", is een eis bij de start.
- Vraagt de vacature een afgeronde vakopleiding (bijv. mbo Elektrotechniek) en is de skill basisvakkennis uit die opleiding die nodig is voor de kerntaken (bijv. technische tekeningen lezen voor een elektromonteur), dan is dat instroom met betrouwbaarheid "midden".

Per item geef je:
- `categorie`: "instroom" of "on_the_job"
- `toelichting`: één korte zin in het Nederlands waarom, verwijzend naar de vacature of het kader
- `betrouwbaarheid`: "hoog" (duidelijk signaal in de tekst), "midden" (redelijk duidelijk) of "laag" (weinig houvast)

Kies alleen "instroom" als de vacature het duidelijk als eis bij de start stelt, of als het om een wettelijke kwalificatie of veiligheidskritische vaardigheid gaat. Is de betrouwbaarheid "laag", kies dan "on_the_job".

Geef ALLEEN JSON terug, precies in dit formaat:
{"keuzes": [{"nummer": 1, "categorie": "instroom", "toelichting": "...", "betrouwbaarheid": "hoog"}]}
