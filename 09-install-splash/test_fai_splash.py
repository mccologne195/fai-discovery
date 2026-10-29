import importlib.machinery
import importlib.util
import re
from argparse import Namespace
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
SPLASH = HERE / "fai-config" / "splash" / "fai-splash"
HOOK = HERE.parent / "01-discovery-client" / "fai-config" / "hooks" / "discovery"


@pytest.fixture
def splash(monkeypatch):
    # Skript ohne .py-Endung laden; Umgebung des Entwicklungsrechners darf nichts beeinflussen
    monkeypatch.delenv("FAI_SPLASH_LANG", raising=False)
    loader = importlib.machinery.SourceFileLoader("fai_splash", str(SPLASH))
    spec = importlib.util.spec_from_loader("fai_splash", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def placeholders(text):
    return re.findall(r"%[sd]", text)


def test_every_text_exists_in_both_languages(splash):
    for key, variants in splash.TEXT.items():
        assert set(variants) == set(splash.LANGUAGES), key
        assert all(v.strip() for v in variants.values()), key


def test_placeholders_match_between_languages(splash):
    for key, variants in splash.TEXT.items():
        assert placeholders(variants["de"]) == placeholders(variants["en"]), key


def test_every_task_has_both_labels(splash):
    for name, label, weight in splash.TASKS:
        assert set(label) == set(splash.LANGUAGES), name
        assert weight > 0


def test_english_text_is_really_english(splash):
    # Schutz vor halb uebersetzten Eintraegen: kein Umlaut im englischen Text
    for key, variants in splash.TEXT.items():
        assert not re.search("[äöüÄÖÜß]", variants["en"]), key
    for name, label, _ in splash.TASKS:
        assert not re.search("[äöüÄÖÜß]", label["en"]), name


def test_language_defaults_to_german(splash, monkeypatch, tmp_path):
    monkeypatch.setattr(splash, "HERE", str(tmp_path))
    assert splash.detect_language() == "de"


def test_language_from_file(splash, monkeypatch, tmp_path):
    monkeypatch.setattr(splash, "HERE", str(tmp_path))
    (tmp_path / "lang").write_text("en\n")
    assert splash.detect_language() == "en"


def test_language_env_overrides_file(splash, monkeypatch, tmp_path):
    monkeypatch.setattr(splash, "HERE", str(tmp_path))
    (tmp_path / "lang").write_text("en\n")
    monkeypatch.setenv("FAI_SPLASH_LANG", "de")
    assert splash.detect_language() == "de"


def test_unknown_language_falls_back_to_german(splash, monkeypatch, tmp_path):
    monkeypatch.setattr(splash, "HERE", str(tmp_path))
    (tmp_path / "lang").write_text("fr\n")
    assert splash.detect_language() == "de"


def say_args(**kw):
    base = dict(kind="info", msg=None, line=None, sub=None, detail=None, pct=None)
    base.update(kw)
    return Namespace(**base)


def written_message(splash, monkeypatch, tmp_path, lang, **kw):
    monkeypatch.setattr(splash, "LOGDIR", str(tmp_path))
    monkeypatch.setattr(splash, "MSG_FILE", str(tmp_path / "msg"))
    monkeypatch.setattr(splash, "LANG", lang)
    assert splash.cmd_say(say_args(**kw)) == 0
    return (tmp_path / "msg").read_text().rstrip("\n").split("\x1f")


@pytest.mark.parametrize("lang,line,sub", [
    ("de", "Warte auf Freigabe", "Bitte das Gerät in der Webkonsole freigeben"),
    ("en", "Waiting for approval", "Please approve the device in the web console"),
])
def test_say_msg_uses_language(splash, monkeypatch, tmp_path, lang, line, sub):
    kind, got_line, got_sub, detail, pct = written_message(
        splash, monkeypatch, tmp_path, lang, kind="wait", msg="waiting", detail="MAC x")
    assert (kind, got_line, got_sub, detail, pct) == ("wait", line, sub, "MAC x", "-1")


def test_say_explicit_text_overrides_msg(splash, monkeypatch, tmp_path):
    parts = written_message(splash, monkeypatch, tmp_path, "en", msg="reporting", sub="Some CPU")
    assert parts[1] == "Reporting device"
    assert parts[2] == "Some CPU"


def test_say_unknown_msg_does_not_fail(splash, monkeypatch, tmp_path):
    parts = written_message(splash, monkeypatch, tmp_path, "en", msg="does_not_exist")
    assert parts[1] == "" and parts[2] == ""


def test_hook_only_uses_known_messages(splash):
    names = set(re.findall(r"splash say .*?-m (\w+)", HOOK.read_text()))
    assert names, "Hook ruft keine Meldungen ueber -m auf"
    for name in names:
        assert "msg.%s.line" % name in splash.TEXT, name


def test_monitor_messages_are_translated(splash, monkeypatch):
    monkeypatch.setattr(splash, "LANG", "en")
    state = splash.State()
    state.monitor("TASKBEGIN partition")
    assert state.st["line"] == "Installation in progress"
    assert state.st["sub"] == "Step 5 of 17: Partitioning disk"
    state.monitor("TASKEND instsoft 3")
    assert state.st["kind"] == "error"
    assert state.st["line"] == "Error in step: Installing packages"
    assert "Alt+F1 (log)" in state.st["sub"]


def test_monitor_messages_german(splash, monkeypatch):
    monkeypatch.setattr(splash, "LANG", "de")
    state = splash.State()
    state.monitor("TASKBEGIN partition")
    assert state.st["sub"] == "Schritt 5 von 17: Festplatte partitionieren"


def test_preview_states_render_in_both_languages(splash, monkeypatch):
    for lang in splash.LANGUAGES:
        monkeypatch.setattr(splash, "LANG", lang)
        states = splash.preview_states()
        assert set(states) == {"boot", "wait", "install", "done", "error"}
        assert all(st["line"] for st in states.values())


def make_font(splash, tmp_path, monkeypatch, data):
    path = tmp_path / "font.psf"
    path.write_bytes(data)
    monkeypatch.setattr(splash, "FONT_CANDIDATES", [str(path)])
    return splash.Font()


def glyph(fill, charsize=16):
    return bytes([fill]) * charsize


def test_font_uses_unicode_table_psf2(splash, tmp_path, monkeypatch):
    import struct
    # Glyph 0 = "a", Glyph 1 = "ä" (Reihenfolge absichtlich NICHT Latin-9), je mit Unicode-Eintrag
    header = b"\x72\xb5\x4a\x86" + struct.pack("<7I", 0, 32, 1, 2, 16, 16, 8)
    table = "a".encode() + b"\xff" + "ä".encode() + b"\xff"
    font = make_font(splash, tmp_path, monkeypatch,
                     header + glyph(0x01) + glyph(0x80) + table)
    assert font.unicode == {ord("a"): 0, ord("ä"): 1}
    assert font.glyph_rows("ä")[0][0] == 1      # Glyph 1 (0x80 = linkes Bit)
    assert font.glyph_rows("a")[0][7] == 1      # Glyph 0 (0x01 = rechtes Bit)


def test_font_uses_unicode_table_psf1(splash, tmp_path, monkeypatch):
    header = b"\x36\x04" + bytes([2, 16])       # mode 2 = hat Unicode-Tabelle, 256 Glyphen sind hier 256
    glyphs = [glyph(0x00)] * 256
    glyphs[7] = glyph(0xff)
    table = b""
    for i in range(256):
        table += (b"\x41\x00" if i == 7 else b"") + b"\xff\xff"   # Glyph 7 = "A"
    font = make_font(splash, tmp_path, monkeypatch, header + b"".join(glyphs) + table)
    assert font.unicode.get(ord("A")) == 7
    assert font.glyph_rows("A")[0] == [1] * 8


def test_font_without_table_falls_back_to_latin9(splash, tmp_path, monkeypatch):
    header = b"\x36\x04" + bytes([0, 16])
    glyphs = [glyph(0x00)] * 256
    glyphs[0xE4] = glyph(0xff)                  # ä im Latin-9-Layout
    font = make_font(splash, tmp_path, monkeypatch, header + b"".join(glyphs))
    assert font.unicode == {}
    assert font.glyph_rows("ä")[0] == [1] * 8


def test_credit_names_fai_and_its_author_in_both_languages(splash):
    for lang in splash.LANGUAGES:
        text = splash.TEXT["credit"][lang]
        assert "FAI" in text and "Thomas Lange" in text and "fai-project.org" in text, lang
