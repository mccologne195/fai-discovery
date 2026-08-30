import os
import time

import localtime


def _set_tz(tz):
    os.environ["TZ"] = tz
    time.tzset()


def test_format_local_converts_utc_to_system_timezone():
    _set_tz("Europe/Berlin")
    try:
        result = localtime.format_local("2026-08-17T18:57:13.530531+00:00")
    finally:
        _set_tz("UTC")

    assert result == "2026-08-17 20:57:13 CEST"


def test_format_local_follows_different_system_timezone():
    _set_tz("America/New_York")
    try:
        result = localtime.format_local("2026-08-17T18:57:13+00:00")
    finally:
        _set_tz("UTC")

    assert result == "2026-08-17 14:57:13 EDT"


def test_format_local_handles_naive_input_as_utc():
    _set_tz("Europe/Berlin")
    try:
        result = localtime.format_local("2026-08-17T18:57:13")
    finally:
        _set_tz("UTC")

    assert result == "2026-08-17 20:57:13 CEST"


def test_format_local_passes_through_empty_value():
    assert localtime.format_local(None) is None
    assert localtime.format_local("") == ""
