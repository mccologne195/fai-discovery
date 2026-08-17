from flask import Blueprint, Response, redirect, render_template, request, url_for

import chboot
import diskconfig
import i18n
import logs
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
        return i18n.t("errors.unknown_mac"), 404

    try:
        profile_list = profiles.load_profiles(profiles.profile_path())
        profile_error = None
    except OSError:
        profile_list = []
        profile_error = i18n.t("approve.error_profile_unreadable", path=profiles.profile_path())

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
        previous_hostname_suggestion=device.get("previous_hostname"),
    )


@bp.route("/approve/<mac>", methods=["POST"])
@require_auth
def approve_submit(username, mac):
    device = storage.get_device(mac)
    if device is None:
        return i18n.t("errors.unknown_mac"), 404

    try:
        profile_list = profiles.load_profiles(profiles.profile_path())
    except OSError:
        return (
            render_template(
                "approve.html",
                device=device,
                profiles=[],
                profile_error=i18n.t("approve.error_profile_unreadable", path=profiles.profile_path()),
                form_error=None,
                type_prefixes=prefixes.load_type_prefixes(),
                location_prefixes=prefixes.load_location_prefixes(),
                serial_suggestion=chboot.suggest_hostname_fragment(device.get("serial")),
                uuid_suggestion=chboot.suggest_hostname_fragment_from_uuid(device.get("uuid")),
                previous_hostname_suggestion=device.get("previous_hostname"),
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
                form_error=i18n.t("approve.error_invalid_form"),
                type_prefixes=prefixes.load_type_prefixes(),
                location_prefixes=prefixes.load_location_prefixes(),
                serial_suggestion=chboot.suggest_hostname_fragment(device.get("serial")),
                uuid_suggestion=chboot.suggest_hostname_fragment_from_uuid(device.get("uuid")),
                previous_hostname_suggestion=device.get("previous_hostname"),
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
                form_error=i18n.t("approve.error_chboot_failed", detail=output),
                type_prefixes=prefixes.load_type_prefixes(),
                location_prefixes=prefixes.load_location_prefixes(),
                serial_suggestion=chboot.suggest_hostname_fragment(device.get("serial")),
                uuid_suggestion=chboot.suggest_hostname_fragment_from_uuid(device.get("uuid")),
                previous_hostname_suggestion=device.get("previous_hostname"),
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
        return i18n.t("errors.invalid_mac"), 400
    if not storage.delete_device(mac):
        return i18n.t("errors.unknown_or_undeletable"), 404
    return redirect(url_for("admin.history"))


@bp.route("/history/<mac>/reinstall", methods=["POST"])
@require_auth
def history_reinstall(username, mac):
    if not chboot.MAC_RE.fullmatch(mac):
        return i18n.t("errors.invalid_mac"), 400

    device = storage.get_device(mac)
    if device is None or device["status"] != "reboot":
        return i18n.t("errors.unknown_or_not_reinstallable"), 404

    ok, output = chboot.run_fai_chboot_discovery(mac)
    if not ok:
        return i18n.t("errors.chboot_failed", detail=output), 502

    storage.mark_reinstalling(mac)
    return redirect(url_for("admin.history"))


@bp.route("/history/<mac>/logs", methods=["GET"])
@require_auth
def history_logs(username, mac):
    if not chboot.MAC_RE.fullmatch(mac):
        return i18n.t("errors.invalid_mac"), 400

    device = storage.get_device(mac)
    if device is None or device["status"] not in ("reboot", "reinstalling"):
        return i18n.t("errors.unknown_or_no_logs"), 404

    install_dir = logs.find_latest_install_dir(logs.log_dir(), device["hostname"])
    if install_dir is None:
        return i18n.t("errors.unknown_or_no_logs"), 404

    log_data = logs.read_install_log(install_dir)
    return render_template(
        "logs.html",
        device=device,
        run_label=install_dir.name,
        log_data=log_data,
    )


@bp.route("/history/<mac>/logs/full", methods=["GET"])
@require_auth
def history_logs_full(username, mac):
    if not chboot.MAC_RE.fullmatch(mac):
        return i18n.t("errors.invalid_mac"), 400

    device = storage.get_device(mac)
    if device is None or device["status"] not in ("reboot", "reinstalling"):
        return i18n.t("errors.unknown_or_no_logs"), 404

    install_dir = logs.find_latest_install_dir(logs.log_dir(), device["hostname"])
    if install_dir is None:
        return i18n.t("errors.unknown_or_no_logs"), 404

    fai_log_path = install_dir / "fai.log"
    if not fai_log_path.is_file():
        return i18n.t("errors.unknown_or_no_logs"), 404

    return Response(fai_log_path.read_text(), mimetype="text/plain")


@bp.route("/discard/<mac>", methods=["POST"])
@require_auth
def discard(username, mac):
    if not chboot.MAC_RE.fullmatch(mac):
        return i18n.t("errors.invalid_mac"), 400

    device = storage.get_device(mac)
    if device is None or device["status"] != "waiting":
        return i18n.t("errors.unknown_or_undiscardable"), 404

    ok, output = chboot.run_fai_chboot_disable(mac)
    if not ok:
        return i18n.t("errors.chboot_failed", detail=output), 502

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
                form_error=i18n.t("discovery.error_no_macs"),
            ),
            400,
        )

    seen = set()
    results = []
    for original in candidates:
        normalized = chboot.normalize_mac(original)
        if normalized is None:
            results.append({"mac": original, "ok": False, "message": i18n.t("discovery.error_invalid_mac")})
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        existing = storage.get_device(normalized)
        if existing is not None and existing["status"] != "discarded":
            results.append({
                "mac": normalized,
                "ok": False,
                "message": i18n.t("discovery.error_already_registered", status=existing["status"]),
            })
            continue
        ok, output = chboot.run_fai_chboot_discovery(normalized)
        results.append({"mac": normalized, "ok": ok, "message": output})

    return render_template("discovery.html", results=results, form_error=None)
