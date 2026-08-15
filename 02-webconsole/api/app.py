from flask import Flask, jsonify, request

import chboot
import diskconfig
import i18n
import storage
from admin import bp as admin_bp
from auth import require_auth

app = Flask(__name__)
app.register_blueprint(admin_bp)
app.jinja_env.globals["t"] = i18n.t
app.jinja_env.globals["current_language"] = i18n.current_language


@app.route("/register", methods=["POST"])
def register():
    data = request.get_json(force=True, silent=True) or {}
    mac = chboot.normalize_mac(data.get("mac", ""))
    if not mac:
        return jsonify({"error": "invalid mac"}), 400

    storage.register_device(
        mac,
        str(data.get("ip", "")),
        str(data.get("cpu", "")),
        str(data.get("ram", "")),
        str(data.get("disk", "")),
        str(data.get("uuid", "")),
        str(data.get("serial", "")),
        str(data.get("firmware", "")),
    )
    return jsonify({"status": "registered"}), 200


@app.route("/status/<path:mac>", methods=["GET"])
def status(mac):
    normalized = chboot.normalize_mac(mac)
    if not normalized:
        return "waiting", 200
    return storage.get_status(normalized), 200


@app.route("/device/<path:mac>", methods=["GET"])
def device(mac):
    normalized = chboot.normalize_mac(mac)
    if not normalized:
        return jsonify({"hostname": None, "classes": None}), 200

    record = storage.get_device(normalized)
    if record is None:
        return jsonify({"hostname": None, "classes": None}), 200

    return jsonify({"hostname": record["hostname"], "classes": record["classes"]}), 200


@app.route("/approve", methods=["POST"])
@require_auth
def approve(username):
    data = request.get_json(force=True, silent=True) or {}
    mac = chboot.normalize_mac(data.get("mac", ""))
    if not mac:
        return jsonify({"error": "invalid mac"}), 400
    device = storage.get_device(mac)
    if device is None:
        return jsonify({"error": "unknown mac"}), 404

    hostname = data.get("hostname", "")
    if not isinstance(hostname, str) or not chboot.HOSTNAME_RE.fullmatch(hostname):
        return jsonify({"error": "invalid hostname"}), 400

    classes = data.get("classes", "")
    if not isinstance(classes, str) or not classes:
        return jsonify({"error": "invalid classes"}), 400
    if not chboot.CLASSES_RE.fullmatch(classes):
        return jsonify({"error": "invalid classes"}), 400

    classes = diskconfig.classes_with_efi_variants(classes, device.get("firmware") or "")

    ok, output = chboot.run_fai_chboot(mac, classes)
    if not ok:
        return jsonify({"error": "fai-chboot failed", "detail": output}), 502

    storage.approve_device(mac, hostname, classes, username)
    return jsonify({"status": "approved"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
