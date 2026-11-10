"""Rooktest van de interface in demo-modus (geen internet of API-sleutel nodig)."""

from streamlit.testing.v1 import AppTest

from src.config import PROJECT_MAP


def _knop(app, label):
    return next(b for b in app.button if b.label == label)


def _start(monkeypatch) -> AppTest:
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    app = AppTest.from_file(str(PROJECT_MAP / "app.py"), default_timeout=60).run()
    assert not app.exception
    app.toggle(key="demo_modus").set_value(True).run()
    _knop(app, "Laad voorbeeld").click().run()
    assert "Logistiek" in app.text_area[0].value
    _knop(app, "Analyseer vacature").click().run()
    assert not app.exception
    return app


def test_demo_modus_toont_resultaat(monkeypatch):
    app = _start(monkeypatch)
    assert any("Resultaat" in s.value for s in app.subheader)


def test_menselijke_review_maakt_profiel_definitief(monkeypatch):
    # Elektromonteur heeft instroomeisen in het vooraf berekende resultaat
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    app = AppTest.from_file(str(PROJECT_MAP / "app.py"), default_timeout=60).run()
    app.toggle(key="demo_modus").set_value(True).run()
    app.selectbox(key="gekozen_voorbeeld").set_value("Elektromonteur").run()
    _knop(app, "Laad voorbeeld").click().run()
    _knop(app, "Analyseer vacature").click().run()

    instroom = len(app.session_state.profiel.instroom())
    assert instroom > 0
    for i in range(instroom):
        _knop(app, "Bevestig instroom").click().run()
    assert not app.exception
    assert all(s.door_mens_bevestigd for s in app.session_state.profiel.instroom())
    assert any("definitief" in s.value for s in app.success)


def test_eigen_tekst_in_demo_modus_geeft_uitleg(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    app = AppTest.from_file(str(PROJECT_MAP / "app.py"), default_timeout=60).run()
    app.toggle(key="demo_modus").set_value(True).run()
    app.text_area(key="vacature").set_value("Dit is een eigen vacature voor een kok. " * 5).run()
    _knop(app, "Analyseer vacature").click().run()
    assert any("demo-modus" in w.value for w in app.warning)
