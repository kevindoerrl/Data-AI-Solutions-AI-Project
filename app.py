"""Streamlit-interface: vacature plakken -> ESCO-skillsprofiel met instroom / on the job.

Starten:  streamlit run app.py
"""

import html
import time

import streamlit as st

from src import pipeline
from src.config import APP_VERSIE, ESCO_VERSIE, VOORBEELD_MAP
from src.demo import laad_vooraf_berekend, zoek_voorbeeld
from src.esco import EscoFout
from src.classify import laad_kader
from src.export import is_definitief, naar_csv, naar_json
from src.llm_providers import LLMFout, kies_provider
from src.models import Profiel, ProfielSkill
from src.uitleg import RUBRIEK_NAMEN, per_regel

st.set_page_config(page_title="Vacature naar ESCO-skillsprofiel", page_icon="🧭", layout="wide")

# Wat extra opmaak: rustige kaarten en duidelijke labels, goed leesbaar op een groot scherm
st.markdown(
    """
    <style>
    .block-container { padding-top: 2rem; max-width: 1400px; }
    .label-hoog   { background:#DDF3E4; color:#0B5D1E; }
    .label-midden { background:#FFF1CC; color:#7A5300; }
    .label-laag   { background:#ECEEF1; color:#3D4450; }
    .label { padding:2px 10px; border-radius:999px; font-size:0.85rem; font-weight:600; }
    .bronzin { border-left:4px solid #C9CED6; padding:4px 12px; color:#3D4450; font-style:italic; }
    mark { background:#FFF1A8; padding:0 2px; }
    .vacaturetekst { white-space:pre-wrap; font-size:0.95rem; line-height:1.55; }
    .regel { border-left:6px solid #C9CED6; padding:6px 12px; margin:6px 0; border-radius:4px; background:#FAFBFC; }
    .regel .zin { font-size:0.98rem; }
    .regel .uitleg { font-size:0.85rem; color:#3D4450; margin-top:3px; }
    .regel-instroom   { border-left-color:#00811F; background:#F1FAF3; }
    .regel-on_the_job { border-left-color:#2F6FDE; background:#F1F5FD; }
    .regel-geen_esco  { border-left-color:#D98A00; background:#FFF8EA; }
    .regel-overgeslagen { border-left-color:#E1E4E8; background:transparent; }
    .regel-overgeslagen .zin { color:#6B7280; }
    .regel-niet_beoordeeld { border-left-color:#C2410C; background:#FFF3EE; }
    .pil { display:inline-block; padding:1px 8px; border-radius:999px; font-size:0.78rem; font-weight:600; margin-right:4px; }
    .pil-instroom { background:#DDF3E4; color:#0B5D1E; }
    .pil-on_the_job { background:#DCE7FB; color:#1E428A; }
    .pil-geen_esco { background:#FFE9BF; color:#7A4B00; }
    .pil-overgeslagen { background:#ECEEF1; color:#3D4450; }
    .pil-niet_beoordeeld { background:#FFE0D1; color:#8A2E07; }
    </style>
    """,
    unsafe_allow_html=True,
)

VOORBEELDEN = {
    "Logistiek medewerker": "logistiek_medewerker.txt",
    "Verzorgende IG": "verzorgende_ig.txt",
    "Elektromonteur": "elektromonteur.txt",
}


# ---------------------------------------------------------------------------
# Hulpfuncties
# ---------------------------------------------------------------------------

def laad_voorbeeld() -> None:
    """Zet de gekozen voorbeeldvacature in het tekstvak."""
    bestand = VOORBEELD_MAP / VOORBEELDEN[st.session_state.gekozen_voorbeeld]
    st.session_state.vacature = bestand.read_text(encoding="utf-8")
    st.session_state.pop("profiel", None)


def markeer(tekst: str, zinnen: list[str]) -> str:
    """Geef de tekst als veilige HTML terug, met de bronzinnen geel gemarkeerd."""
    veilig = html.escape(tekst)
    for zin in sorted(set(zinnen), key=len, reverse=True):
        if zin:
            veilig = veilig.replace(html.escape(zin), f"<mark>{html.escape(zin)}</mark>")
    return veilig


def label_html(betrouwbaarheid: str) -> str:
    return f'<span class="label label-{betrouwbaarheid}">betrouwbaarheid: {betrouwbaarheid}</span>'


def bevestig(index: int) -> None:
    st.session_state.profiel.skills[index].door_mens_bevestigd = True


def zet_om(index: int) -> None:
    skill = st.session_state.profiel.skills[index]
    skill.categorie = "on_the_job"
    skill.door_mens_bevestigd = True
    skill.toelichting = "Door een mens omgezet van instroom naar on the job. " + skill.toelichting


def herstel(index: int) -> None:
    """Maak de beslissing van de mens ongedaan (terug naar het voorstel van de tool)."""
    origineel = st.session_state.origineel.skills[index]
    st.session_state.profiel.skills[index] = origineel.model_copy(deep=True)


def bewaar_resultaat(profiel: Profiel) -> None:
    st.session_state.profiel = profiel
    st.session_state.origineel = profiel.model_copy(deep=True)  # voor "ongedaan maken"


def toon_skillkaart(skill: ProfielSkill, index: int) -> None:
    with st.container(border=True):
        st.markdown(f"**{skill.esco_label}**  \n{label_html(skill.betrouwbaarheid)}", unsafe_allow_html=True)
        st.write(skill.toelichting)
        zinnen = skill.alle_bronzinnen()
        with st.expander("Bronzin uit de vacature" if len(zinnen) == 1 else f"Bronzinnen uit de vacature ({len(zinnen)})"):
            for zin in zinnen:
                st.markdown(f'<div class="bronzin">{html.escape(zin)}</div>', unsafe_allow_html=True)
            st.caption(f"ESCO: [{skill.esco_uri}]({skill.esco_uri})")
        with st.expander("Hoe is dit besloten?"):
            st.markdown(beslissing_markdown(skill))

        if skill.categorie == "instroom" and not skill.door_mens_bevestigd:
            links, rechts = st.columns(2)
            links.button("Bevestig instroom", key=f"bev_{index}", on_click=bevestig, args=(index,), use_container_width=True)
            rechts.button("Zet om naar on the job", key=f"om_{index}", on_click=zet_om, args=(index,), use_container_width=True)
        elif skill.door_mens_bevestigd:
            tekst = "✅ Instroomeis bevestigd door een mens" if skill.categorie == "instroom" else "↪ Door een mens omgezet naar on the job"
            links, rechts = st.columns([3, 1])
            links.markdown(tekst)
            rechts.button("Ongedaan maken", key=f"herstel_{index}", on_click=herstel, args=(index,), use_container_width=True)


CATEGORIE_NAAM = {"instroom": "instroom", "on_the_job": "on the job", None: "geen advies"}


def beslissing_markdown(skill: ProfielSkill) -> str:
    """De stappen die tot de indeling hebben geleid, in gewone taal."""
    rubrieken = sorted({RUBRIEK_NAMEN[r] for r in [skill.rubriek, *skill.extra_rubrieken]})
    woorden = ", ".join(f'"{w}"' for w in skill.signaalwoorden) or "geen"
    model = (
        f"{CATEGORIE_NAAM[skill.model_categorie]} (betrouwbaarheid {skill.betrouwbaarheid})"
        if skill.model_categorie else "geen oordeel"
    )
    regels = [
        f"1. **Kopje in de vacature:** {', '.join(rubrieken)}",
        f"2. **Signaalwoorden:** {woorden}",
        f"3. **Regels** (classificatiekader): {CATEGORIE_NAAM[skill.regel_advies]}, want {skill.regel_reden or 'geen signaal'}",
        f"4. **AI-model:** {model}",
    ]
    if skill.vangnet:
        regels.append(f"5. **Vangnet:** {skill.vangnet}")
    regels.append(f"\n**Uitkomst: {CATEGORIE_NAAM[skill.categorie]}**")
    return "\n".join(regels)


def _regel_html(r) -> str:
    """Eén regel van de vacature, met wat de tool ermee deed."""
    e = html.escape
    if r.status in ("overgeslagen", "niet_beoordeeld"):
        woord = "Overgeslagen" if r.status == "overgeslagen" else "Niet beoordeeld"
        return (
            f'<div class="regel regel-{r.status}"><div class="zin">{e(r.zin)}</div>'
            f'<div class="uitleg">{woord}: {e(r.reden)}</div></div>'
        )

    kop = f"Kopje: {e(RUBRIEK_NAMEN.get(r.rubriek or 'overig', 'overig'))}"
    if r.signaalwoorden:
        kop += " · signaalwoorden: " + ", ".join(f"<b>{e(w)}</b>" for w in r.signaalwoorden)
    regels = [kop]
    for s in r.stappen:
        if s.esco_uri:
            tekst = (
                f'<span class="pil pil-{s.categorie}">{e(CATEGORIE_NAAM[s.categorie])}</span>'
                f"„{e(s.uitspraak)}” → ESCO: <b>{e(s.esco_label)}</b> (gekozen uit {len(s.kandidaten)} kandidaten)"
            )
            if s.samengevoegd:
                tekst += " · samen beoordeeld met andere zinnen over dezelfde skill"
        else:
            voorstel = ", ".join(e(k) for k in s.kandidaten[:3]) or "niets"
            tekst = (
                f'<span class="pil pil-geen_esco">geen ESCO-skill</span>„{e(s.uitspraak)}”: '
                f"ESCO stelde voor: <i>{voorstel}</i>; geen daarvan past. "
                f"Volgens de regels: {e(CATEGORIE_NAAM[s.regel_advies])} ({e(s.regel_reden)})."
            )
        regels.append(tekst)
    hoofd = next((s.categorie for s in r.stappen if s.categorie), None)
    klasse = hoofd if r.status == "skill" and hoofd else "geen_esco"
    return (
        f'<div class="regel regel-{klasse}"><div class="zin">{e(r.zin)}</div>'
        + "".join(f'<div class="uitleg">{x}</div>' for x in regels)
        + "</div>"
    )


def toon_achter_de_schermen(profiel: Profiel) -> None:
    """Regel voor regel: wat deed de tool met elke zin uit de vacature, en waarom?"""
    if not profiel.uitleg:
        st.info("Dit resultaat is gemaakt met een oudere versie van de tool en bevat nog geen uitleg per regel.")
        return
    regels = per_regel(profiel)
    n = {s: sum(r.status == s for r in regels) for s in ("skill", "geen_esco", "overgeslagen", "niet_beoordeeld")}
    st.markdown(
        f"De tool las **{len(regels)} regels**: {n['skill']} leverden een ESCO-skill op, "
        f"{n['geen_esco']} bevatten een skill of eis zonder passende ESCO-skill, "
        f"{n['overgeslagen']} zijn bewust overgeslagen"
        + (f" en {n['niet_beoordeeld']} heeft het model niet genoemd." if n["niet_beoordeeld"] else ".")
    )
    st.markdown(
        '<span class="pil pil-instroom">skill · instroom</span>'
        '<span class="pil pil-on_the_job">skill · on the job</span>'
        '<span class="pil pil-geen_esco">geen passende ESCO-skill</span>'
        '<span class="pil pil-overgeslagen">overgeslagen</span>'
        + ('<span class="pil pil-niet_beoordeeld">niet beoordeeld</span>' if n["niet_beoordeeld"] else ""),
        unsafe_allow_html=True,
    )
    st.markdown("".join(_regel_html(r) for r in regels), unsafe_allow_html=True)


def toon_aannames() -> None:
    """De vaste regels en aannames van de tool; de signaalwoorden komen uit config/classificatiekader.yaml."""
    kader = laad_kader()
    st.markdown(
        """
**Welke zinnen leveren een skill op?**
- Elke regel van de vacature wordt bekeken. Kopjes, bedrijfsinformatie, arbeidsvoorwaarden (contract,
  bedrijfsbus) en sollicitatie-informatie leveren geen skill op.
- Taken ("je legt installaties aan"), eisen en wensen ("… is een pré") leveren wél skills op.
- Een certificaat of diploma wordt vertaald naar de vaardigheid erachter (VCA → veiligheidsnormen toepassen).
- Alleen skills die de **ESCO-zoekfunctie zelf** voorstelt, kunnen gekozen worden. Past er geen, dan is het
  "geen passende ESCO-skill": een slechte koppeling is erger dan geen koppeling.
- Gaan meerdere zinnen over dezelfde ESCO-skill, dan worden ze **samen** beoordeeld.

**Instroom of on the job?**
1. **Bij twijfel altijd on the job.** Een onterechte instroomeis sluit werkzoekenden uit.
2. Signaalwoorden in de zin gaan voor (zie hieronder). Staan er signalen voor allebei in, dan is dat twijfel.
3. Geen signaalwoord? Dan telt het kopje: onder *wat vragen wij* is het een eis, onder *wat bieden wij* leer je
   het op het werk. Onder *wat ga je doen* zegt het kopje niets.
4. Het AI-model weegt dit samen met het classificatiekader. Daarna gelden vangnetten: zegt het model instroom
   met lage betrouwbaarheid, of vinden de regels een leer-signaal, dan wordt het on the job.
5. Elke instroomeis moet door een mens worden bevestigd.
"""
    )
    links, rechts = st.columns(2)
    with links:
        st.markdown("**Signaalwoorden voor instroom**")
        st.write(", ".join(kader["categorieen"]["instroom"]["signaalwoorden"]))
    with rechts:
        st.markdown("**Signaalwoorden voor on the job**")
        st.write(", ".join(kader["categorieen"]["on_the_job"]["signaalwoorden"]))
    st.caption("Het team kan deze regels aanpassen in config/classificatiekader.yaml, zonder code te wijzigen.")


def toon_resultaat(profiel: Profiel) -> None:
    st.divider()
    st.subheader("Resultaat")
    tab_profiel, tab_schermen, tab_aannames = st.tabs(["Skillsprofiel", "Achter de schermen", "Aannames van de tool"])
    with tab_profiel:
        toon_profiel(profiel)
    with tab_schermen:
        toon_achter_de_schermen(profiel)
    with tab_aannames:
        toon_aannames()


def toon_profiel(profiel: Profiel) -> None:
    instroom, otj = profiel.instroom(), profiel.on_the_job()

    # Herkend beroep
    if profiel.beroep:
        st.markdown(f"**Herkend ESCO-beroep:** [{profiel.beroep.label}]({profiel.beroep.uri})")
    else:
        st.markdown("**Herkend ESCO-beroep:** geen passend beroep gevonden")

    # Teller
    a, b, c = st.columns(3)
    a.metric("Skills", len(profiel.skills))
    b.metric("Instroom", len(instroom))
    c.metric("On the job", len(otj))
    st.markdown(f"**{len(profiel.skills)} skills: {len(instroom)} instroom, {len(otj)} on the job**")

    open_eisen = [s for s in instroom if not s.door_mens_bevestigd]
    if not instroom:
        st.success("Geen instroomeisen om te controleren. Het profiel is definitief.", icon="✅")
    elif open_eisen:
        st.info(
            f"Nog {len(open_eisen)} instroomeis(en) te controleren. Bevestig elke eis of zet hem om naar "
            "on the job. Pas daarna is het profiel definitief.",
            icon="👤",
        )
    else:
        st.success("Alle instroomeisen zijn door een mens gecontroleerd. Het profiel is definitief.", icon="✅")

    # Twee kolommen: instroom en on the job
    kol_in, kol_otj = st.columns(2, gap="large")
    with kol_in:
        st.markdown("### Instroom")
        st.caption("Nodig bij de start")
        if not instroom:
            st.write("Geen instroomeisen.")
        for i, skill in enumerate(profiel.skills):
            if skill.categorie == "instroom":
                toon_skillkaart(skill, i)
    with kol_otj:
        st.markdown("### On the job")
        st.caption("Kan op de werkvloer geleerd worden")
        if not otj:
            st.write("Geen on-the-job-skills.")
        for i, skill in enumerate(profiel.skills):
            if skill.categorie == "on_the_job":
                toon_skillkaart(skill, i)

    # Mogelijk ontbrekende essentiële skills van het beroep
    st.markdown("### Mogelijk ontbrekende essentiële skills")
    st.caption(
        "Deze skills zijn volgens ESCO essentieel voor het herkende beroep, maar komen niet in de vacature voor. "
        "Ze worden niet automatisch toegevoegd."
    )
    if profiel.mogelijk_ontbrekend:
        st.markdown("\n".join(f"- [{s.label}]({s.uri})" for s in profiel.mogelijk_ontbrekend))
    else:
        st.write("Geen.")

    # Uitspraken zonder passende ESCO-skill
    zonder_esco = [u for u in profiel.uitleg if not u.gekozen_uri]
    if zonder_esco:
        with st.expander(f"Skills en eisen zonder passende ESCO-skill ({len(zonder_esco)})"):
            st.caption(
                "Deze staan wel in de vacature, maar ESCO heeft er geen passende skill voor (bijvoorbeeld een "
                "diploma of registratie). Ze staan daarom niet in het profiel. Zie ook 'Achter de schermen'."
            )
            for u in zonder_esco:
                st.markdown(f"- **{u.uitspraak}** ({CATEGORIE_NAAM[u.regel_advies]} volgens de regels) — _{u.bronzin}_")
    elif profiel.niet_gekoppeld:
        with st.expander(f"Uitspraken zonder passende ESCO-skill ({len(profiel.niet_gekoppeld)})"):
            for u in profiel.niet_gekoppeld:
                st.markdown(f"- **{u.uitspraak}** — _{u.bronzin}_")

    # Privacy en brontekst
    with st.expander(f"Verwijderde persoonsgegevens ({len(profiel.verwijderd)})"):
        if profiel.verwijderd:
            for v in profiel.verwijderd:
                st.markdown(f"- {v.soort}: `{v.waarde}`")
        else:
            st.write("Er zijn geen persoonsgegevens gevonden.")
    with st.expander("Vacaturetekst met gemarkeerde bronzinnen"):
        tekst = markeer(profiel.schone_tekst, [z for s in profiel.skills for z in s.alle_bronzinnen()])
        st.markdown(f'<div class="vacaturetekst">{tekst}</div>', unsafe_allow_html=True)

    # Export
    st.markdown("### Exporteren")
    definitief = is_definitief(profiel)
    status = "definitief" if definitief else "concept"
    if not definitief:
        st.caption("Nog niet alle instroomeisen zijn gecontroleerd. Je kunt nu alleen een **concept** downloaden.")
    naam = (profiel.functietitel or "profiel").lower().replace(" ", "_")
    links, rechts = st.columns(2)
    links.download_button(
        f"Download {status} als CSV", naar_csv(profiel), file_name=f"skillsprofiel_{naam}_{status}.csv",
        mime="text/csv", use_container_width=True, type="primary" if definitief else "secondary",
    )
    rechts.download_button(
        f"Download {status} als JSON", naar_json(profiel), file_name=f"skillsprofiel_{naam}_{status}.json",
        mime="application/json", use_container_width=True, type="primary" if definitief else "secondary",
    )

    st.caption(
        f"Model: {profiel.metadata.model} · ESCO {profiel.metadata.esco_versie} · "
        f"app {profiel.metadata.app_versie} · {profiel.metadata.datum}"
    )


# ---------------------------------------------------------------------------
# Pagina
# ---------------------------------------------------------------------------

with st.sidebar:
    st.header("Instellingen")
    demo_modus = st.toggle(
        "Demo-modus",
        key="demo_modus",
        help="Toont vooraf berekende resultaten voor de drie voorbeeldvacatures, zonder live AI- of ESCO-aanroepen.",
    )
    if demo_modus:
        st.caption("Demo-modus staat aan: alleen de drie voorbeeldvacatures werken.")
    try:
        provider = kies_provider()
        st.write(f"**AI-model:** {provider.omschrijving}")
    except LLMFout as fout:
        provider = None
        st.error(str(fout))
    st.write(f"**ESCO-versie:** {ESCO_VERSIE} (Nederlands)")
    st.caption(f"App-versie {APP_VERSIE}")

st.title("Vacature → ESCO-skillsprofiel")
st.markdown(
    "Plak een Nederlandstalige vacature. De tool maakt er een skillsprofiel van op basis van de Europese "
    "**ESCO**-classificatie, en geeft per skill aan of die nodig is **bij instroom** of **on the job** geleerd kan worden."
)
st.info(
    "Deze tool gebruikt AI. De uitkomst is een voorstel; een mens beslist. De tool beoordeelt geen kandidaten.",
    icon="ℹ️",
)

links, rechts = st.columns([3, 1])
with rechts:
    st.selectbox("Voorbeeldvacature", list(VOORBEELDEN), key="gekozen_voorbeeld")
    st.button("Laad voorbeeld", on_click=laad_voorbeeld, use_container_width=True)
    st.caption("De voorbeelden zijn fictief en zelf geschreven.")
with links:
    st.text_area("Vacaturetekst", key="vacature", height=320, placeholder="Plak hier de vacaturetekst…")

if st.button("Analyseer vacature", type="primary", disabled=provider is None and not demo_modus):
    tekst = st.session_state.get("vacature", "").strip()
    if len(tekst) < 50:
        st.warning("Plak eerst een vacaturetekst (minimaal een paar zinnen).")
    elif demo_modus:
        naam = zoek_voorbeeld(tekst)
        profiel = laad_vooraf_berekend(naam) if naam else None
        if profiel is None:
            st.warning(
                "In de demo-modus werken alleen de drie voorbeeldvacatures (ongewijzigd). "
                "Laad een voorbeeld, of zet de demo-modus uit voor een live analyse."
            )
        else:
            with st.status("Bezig met analyseren (demo-modus)…", expanded=True) as status:
                for i, stap in enumerate(pipeline.STAPPEN):
                    status.write(f"Stap {i + 1} van {len(pipeline.STAPPEN)}: {stap}…")
                    time.sleep(0.4)  # korte pauze zodat bezoekers de stappen kunnen volgen
                status.update(label="Analyse klaar (vooraf berekend resultaat)", state="complete", expanded=False)
            bewaar_resultaat(profiel)
    else:
        with st.status("Bezig met analyseren…", expanded=True) as status:

            def voortgang(stap: int, bericht: str) -> None:
                status.write(f"Stap {stap + 1} van {len(pipeline.STAPPEN)}: {bericht}…")

            try:
                bewaar_resultaat(pipeline.analyseer(tekst, provider=provider, voortgang=voortgang))
                status.update(label="Analyse klaar", state="complete", expanded=False)
            except (LLMFout, EscoFout) as fout:
                status.update(label="Er ging iets mis", state="error")
                st.error(f"{fout} Tip: zet de demo-modus aan in de zijbalk.")

if "profiel" in st.session_state:
    toon_resultaat(st.session_state.profiel)
