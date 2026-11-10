"""Rooktest: de Streamlit-app start zonder fouten en toont het (dummy)resultaat."""

from streamlit.testing.v1 import AppTest

from src.config import PROJECT_MAP


def test_app_start_en_analyseert_voorbeeld(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    app = AppTest.from_file(str(PROJECT_MAP / "app.py"), default_timeout=60).run()
    assert not app.exception

    # Voorbeeld laden en analyseren
    app.button[0].click().run()  # "Laad voorbeeld"
    assert "Logistiek" in app.text_area[0].value
    analyseer = next(b for b in app.button if b.label == "Analyseer vacature")
    analyseer.click().run()
    assert not app.exception
    assert any("Resultaat" in s.value for s in app.subheader)
