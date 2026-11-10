"""Streamlit-interface: vacature plakken -> ESCO-skillsprofiel met instroom / on the job.

Starten:  streamlit run app.py
"""

import html

import streamlit as st

from src import pipeline
from src.config import APP_VERSIE, ESCO_VERSIE, VOORBEELD_MAP
from src.esco import EscoFout
from src.export import is_definitief, naar_csv, naar_json
from src.llm_providers import LLMFout, kies_provider
from src.models import Profiel, ProfielSkill

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
        with st.expander("Bronzin uit de vacature"):
            st.markdown(f'<div class="bronzin">{html.escape(skill.bronzin)}</div>', unsafe_allow_html=True)
            st.caption(f"ESCO: [{skill.esco_uri}]({skill.esco_uri})")

        if skill.categorie == "instroom" and not skill.door_mens_bevestigd:
            links, rechts = st.columns(2)
            links.button("Bevestig instroom", key=f"bev_{index}", on_click=bevestig, args=(index,), use_container_width=True)
            rechts.button("Zet om naar on the job", key=f"om_{index}", on_click=zet_om, args=(index,), use_container_width=True)
        elif skill.door_mens_bevestigd:
            tekst = "✅ Instroomeis bevestigd door een mens" if skill.categorie == "instroom" else "↪ Door een mens omgezet naar on the job"
            links, rechts = st.columns([3, 1])
            links.markdown(tekst)
            rechts.button("Ongedaan maken", key=f"herstel_{index}", on_click=herstel, args=(index,), use_container_width=True)


def toon_resultaat(profiel: Profiel) -> None:
    instroom, otj = profiel.instroom(), profiel.on_the_job()

    st.divider()
    st.subheader("Resultaat")

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
    if open_eisen:
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
    if profiel.niet_gekoppeld:
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
        tekst = markeer(profiel.schone_tekst, [s.bronzin for s in profiel.skills])
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

if st.button("Analyseer vacature", type="primary", disabled=provider is None):
    tekst = st.session_state.get("vacature", "").strip()
    if len(tekst) < 50:
        st.warning("Plak eerst een vacaturetekst (minimaal een paar zinnen).")
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
