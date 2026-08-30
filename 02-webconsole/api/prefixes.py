import os

import chboot

TYPE_PREFIXES_ENV = "FAI_DISCOVERY_TYPE_PREFIXES"
LOCATION_PREFIXES_ENV = "FAI_DISCOVERY_LOCATION_PREFIXES"


def parse_prefixes(raw):
    result = []
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        code, _, label = item.partition(":")
        code = code.strip()
        label = label.strip()
        if not code:
            continue
        slug = chboot.suggest_hostname_fragment(code)
        if not slug:
            continue
        result.append({"code": code, "label": label or code, "slug": slug})
    return result


def load_type_prefixes():
    return parse_prefixes(os.environ.get(TYPE_PREFIXES_ENV, ""))


def load_location_prefixes():
    return parse_prefixes(os.environ.get(LOCATION_PREFIXES_ENV, ""))
