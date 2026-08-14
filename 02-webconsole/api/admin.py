from flask import Blueprint, redirect, render_template, request, url_for

import chboot
import diskconfig
import prefixes
import profiles
import storage
from auth import require_auth

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.route("/", methods=["GET"])
@require_auth
def dashboard(username):
    devices = storage.list_waiting_devices()
    return render_template("dashboard.html", devices=devices, username=username)


@bp.route("/approve/<mac>", methods=["GET"])
@require_auth
def approve_form(username, mac):
    device = storage.get_device(mac)
    if device is None:
        return "Unbekannte MAC", 404

    try:
        profile_list = profiles.load_profiles(profiles.profile_path())
        profile_error = None
    except OSError:
        profile_list = []
        profile_error = "Profil-Datei nicht lesbar: " + profiles.profile_path()

    return render_template(
        "approve.html",
        device=device,
        profiles=profile_list,
        profile_error=profile_error,
        form_error=None,
        type_prefixes=prefixes.load_type_prefixes(),
        location_prefixes=prefixes.load_location_prefixes(),
        serial_suggestion=chboot.suggest_hostname_fragment(device.get("serial")),
        uuid_suggestion=chboot.suggest_hostname_fragment_from_uuid(device.get("uuid")),
    )


@bp.route("/approve/<mac>", methods=["POST"])
@require_auth
def approve_submit(username, mac):
    device = storage.get_device(mac)
    if device is None:
        return "Unbekannte MAC", 404

    try:
        profile_list = profiles.load_profiles(profiles.profile_path())
    except OSError:
        return (
            render_template(
                "approve.html",
                device=device,
                profiles=[],
                profile_error="Profil-Datei nicht lesbar: " + profiles.profile_path(),
                form_error=None,
                type_prefixes=prefixes.load_type_prefixes(),
                location_prefixes=prefixes.load_location_prefixes(),
                serial_suggestion=chboot.suggest_hostname_fragment(device.get("serial")),
                uuid_suggestion=chboot.suggest_hostname_fragment_from_uuid(device.get("uuid")),
            ),
            500,
        )

    hostname = request.form.get("hostname", "").strip()
    profile_name = request.form.get("profile", "")
    matching = [p for p in profile_list if p["name"] == profile_name]

    if not chboot.HOSTNAME_RE.fullmatch(hostname) or not matching:
        return (
            render_template(
                "approve.html",
                device=device,
                profiles=profile_list,
                profile_error=None,
                form_error=(
                    "Bitte einen gültigen Hostnamen eingeben "
                    "(nur Kleinbuchstaben, Ziffern, Bindestriche; muss mit Buchstabe oder "
                    "Ziffer beginnen und enden; max. 63 Zeichen) und ein Profil auswählen."
                ),
                type_prefixes=prefixes.load_type_prefixes(),
                location_prefixes=prefixes.load_location_prefixes(),
                serial_suggestion=chboot.suggest_hostname_fragment(device.get("serial")),
                uuid_suggestion=chboot.suggest_hostname_fragment_from_uuid(device.get("uuid")),
            ),
            400,
        )

    classes = matching[0]["classes"]
    classes = diskconfig.classes_with_efi_variants(classes, device.get("firmware") or "")
    ok, output = chboot.run_fai_chboot(mac, classes)
    if not ok:
        return (
            render_template(
                "approve.html",
                device=device,
                profiles=profile_list,
                profile_error=None,
                form_error="fai-chboot fehlgeschlagen: " + output,
                type_prefixes=prefixes.load_type_prefixes(),
                location_prefixes=prefixes.load_location_prefixes(),
                serial_suggestion=chboot.suggest_hostname_fragment(device.get("serial")),
                uuid_suggestion=chboot.suggest_hostname_fragment_from_uuid(device.get("uuid")),
            ),
            502,
        )

    storage.approve_device(mac, hostname, classes, username)
    return redirect(url_for("admin.dashboard"))


@bp.route("/history", methods=["GET"])
@require_auth
def history(username):
    query = request.args.get("q", "").strip()
    records = storage.list_history(query=query)
    return render_template("history.html", records=records, query=query)


@bp.route("/history/<mac>/delete", methods=["POST"])
@require_auth
def history_delete(username, mac):
    if not chboot.MAC_RE.fullmatch(mac):
        return "Ungültige MAC-Adresse", 400
    if not storage.delete_device(mac):
        return "Unbekannter oder nicht löschbarer Eintrag", 404
    return redirect(url_for("admin.history"))


@bp.route("/discard/<mac>", methods=["POST"])
@require_auth
def discard(username, mac):
    if not chboot.MAC_RE.fullmatch(mac):
        return "Ungültige MAC-Adresse", 400

    device = storage.get_device(mac)
    if device is None or device["status"] != "waiting":
        return "Unbekanntes oder nicht verwerfbares Gerät", 404

    ok, output = chboot.run_fai_chboot_disable(mac)
    if not ok:
        return "fai-chboot fehlgeschlagen: " + output, 502

    storage.discard_waiting_device(mac)
    return redirect(url_for("admin.dashboard"))


@bp.route("/help", methods=["GET"])
@require_auth
def help_page(username):
    return render_template("help.html")


@bp.route("/discovery", methods=["GET"])
@require_auth
def discovery_form(username):
    return render_template("discovery.html", results=None, form_error=None)


@bp.route("/discovery", methods=["POST"])
@require_auth
def discovery_submit(username):
    raw = request.form.get("macs", "")
    candidates = [item.strip() for item in raw.split(",")]
    candidates = [item for item in candidates if item]

    if not candidates:
        return (
            render_template(
                "discovery.html",
                results=None,
                form_error="Bitte mindestens eine MAC-Adresse eingeben.",
            ),
            400,
        )

    seen = set()
    results = []
    for original in candidates:
        normalized = chboot.normalize_mac(original)
        if normalized is None:
            results.append({"mac": original, "ok": False, "message": "ungültiges MAC-Format"})
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        existing = storage.get_device(normalized)
        if existing is not None and existing["status"] != "discarded":
            results.append({
                "mac": normalized,
                "ok": False,
                "message": "Gerät ist bereits registriert (Status: " + existing["status"] + ") — Discovery-Trigger nur für unregistrierte Geräte.",
            })
            continue
        ok, output = chboot.run_fai_chboot_discovery(normalized)
        results.append({"mac": normalized, "ok": ok, "message": output})

    return render_template("discovery.html", results=results, form_error=None)
