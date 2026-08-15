import i18n


def test_current_language_defaults_to_de(monkeypatch):
    monkeypatch.delenv("FAI_DISCOVERY_LANGUAGE", raising=False)
    assert i18n.current_language() == "de"


def test_current_language_reads_env_var(monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_LANGUAGE", "en")
    assert i18n.current_language() == "en"


def test_current_language_falls_back_to_de_for_invalid_value(monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_LANGUAGE", "fr")
    assert i18n.current_language() == "de"


def test_t_returns_translation_for_current_language(monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_LANGUAGE", "en")
    assert i18n.t("nav.dashboard") == "Dashboard"
    monkeypatch.setenv("FAI_DISCOVERY_LANGUAGE", "de")
    assert i18n.t("nav.dashboard") == "Dashboard"
    assert i18n.t("nav.history") == "Historie"
    monkeypatch.setenv("FAI_DISCOVERY_LANGUAGE", "en")
    assert i18n.t("nav.history") == "History"


def test_t_interpolates_kwargs(monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_LANGUAGE", "en")
    assert i18n.t("approve.error_chboot_failed", detail="boom") == "fai-chboot failed: boom"
