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
