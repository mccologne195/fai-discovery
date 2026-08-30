import prefixes


def test_parse_prefixes_extracts_code_and_label():
    result = prefixes.parse_prefixes("NB:Notebook,DT:Desktop,SRV:Server")
    assert result == [
        {"code": "NB", "label": "Notebook", "slug": "nb"},
        {"code": "DT", "label": "Desktop", "slug": "dt"},
        {"code": "SRV", "label": "Server", "slug": "srv"},
    ]


def test_parse_prefixes_uses_code_as_label_when_colon_missing():
    result = prefixes.parse_prefixes("NB,DT")
    assert result == [
        {"code": "NB", "label": "NB", "slug": "nb"},
        {"code": "DT", "label": "DT", "slug": "dt"},
    ]


def test_parse_prefixes_strips_whitespace_around_entries():
    result = prefixes.parse_prefixes(" NB : Notebook , DT : Desktop ")
    assert result == [
        {"code": "NB", "label": "Notebook", "slug": "nb"},
        {"code": "DT", "label": "Desktop", "slug": "dt"},
    ]


def test_parse_prefixes_skips_empty_entries():
    result = prefixes.parse_prefixes("NB:Notebook,,DT:Desktop,")
    assert result == [
        {"code": "NB", "label": "Notebook", "slug": "nb"},
        {"code": "DT", "label": "Desktop", "slug": "dt"},
    ]


def test_parse_prefixes_skips_entry_with_empty_code():
    result = prefixes.parse_prefixes(":Notebook,DT:Desktop")
    assert result == [{"code": "DT", "label": "Desktop", "slug": "dt"}]


def test_parse_prefixes_empty_string_returns_empty_list():
    assert prefixes.parse_prefixes("") == []


def test_parse_prefixes_skips_entry_whose_code_does_not_normalize():
    result = prefixes.parse_prefixes("!!!:Broken,DT:Desktop")
    assert result == [{"code": "DT", "label": "Desktop", "slug": "dt"}]


def test_parse_prefixes_normalizes_unicode_code_to_ascii_slug():
    result = prefixes.parse_prefixes("Büro:Hauptbüro")
    assert result == [{"code": "Büro", "label": "Hauptbüro", "slug": "b-ro"}]


def test_load_type_prefixes_uses_env_var(monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_TYPE_PREFIXES", "NB:Notebook,DT:Desktop")
    assert prefixes.load_type_prefixes() == [
        {"code": "NB", "label": "Notebook", "slug": "nb"},
        {"code": "DT", "label": "Desktop", "slug": "dt"},
    ]


def test_load_type_prefixes_default_empty(monkeypatch):
    monkeypatch.delenv("FAI_DISCOVERY_TYPE_PREFIXES", raising=False)
    assert prefixes.load_type_prefixes() == []


def test_load_location_prefixes_uses_env_var(monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_LOCATION_PREFIXES", "K:Köln,B:Berlin")
    assert prefixes.load_location_prefixes() == [
        {"code": "K", "label": "Köln", "slug": "k"},
        {"code": "B", "label": "Berlin", "slug": "b"},
    ]


def test_load_location_prefixes_default_empty(monkeypatch):
    monkeypatch.delenv("FAI_DISCOVERY_LOCATION_PREFIXES", raising=False)
    assert prefixes.load_location_prefixes() == []
