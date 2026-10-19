import os
from pathlib import Path

PROFILE_FILE_ENV = "FAI_DISCOVERY_PROFILE_FILE"
DEFAULT_PROFILE_FILE = "/srv/fai/config/class/example.profile"


def profile_path():
    return os.environ.get(PROFILE_FILE_ENV, DEFAULT_PROFILE_FILE)


def parse_profiles(text):
    profiles_found = []
    for block in text.split("\n\n"):
        name = None
        classes = None
        for line in block.splitlines():
            line = line.strip()
            if line.startswith("Name:"):
                name = line[len("Name:"):].strip()
            elif line.startswith("Classes:"):
                classes = line[len("Classes:"):].strip()
        if name and classes:
            profiles_found.append({"name": name, "classes": classes})
    return profiles_found


def load_profiles(path):
    text = Path(path).read_text()
    return parse_profiles(text)


def parse_default(text):
    # "Default: <Name>" ist die FAI-Profil-Konvention fuer den vorausgewaehlten
    # Eintrag; parse_profiles() ueberspringt diesen Block, weil er weder Name:
    # noch Classes: enthaelt.
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("Default:"):
            return line[len("Default:"):].strip() or None
    return None


def load_default_profile(path):
    # Nur ein Default, der als Profil existiert, wird vorausgewaehlt - sonst
    # bleibt der Platzhalter, damit nie ein Name ohne passende Classes
    # vorbelegt ist. Unlesbare Datei: kein Default (der Fehler wird beim
    # Laden der Profile ohnehin angezeigt).
    try:
        text = Path(path).read_text()
    except OSError:
        return None
    name = parse_default(text)
    if name and any(p["name"] == name for p in parse_profiles(text)):
        return name
    return None
