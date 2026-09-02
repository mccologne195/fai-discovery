import chboot


class FakeResult:
    def __init__(self, returncode, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_run_fai_chboot_success_calls_wrapper_via_sudo(monkeypatch):
    monkeypatch.setenv(chboot.NFS_ROOT_ENV, "nfs://fai.example.com/srv/fai/config")
    calls = []

    def fake_runner(cmd, capture_output, text):
        calls.append(cmd)
        return FakeResult(0, stdout="switched")

    ok, output = chboot.run_fai_chboot("aa:bb:cc:dd:ee:ff", "FAIBASE DEBIAN", runner=fake_runner)

    assert ok is True
    assert output == "switched"
    assert calls == [[
        "sudo", chboot.CHBOOT_WRAPPER, "approve",
        "aa:bb:cc:dd:ee:ff", "FAIBASE DEBIAN", "nfs://fai.example.com/srv/fai/config",
        "0", "1", "",
    ]]


def test_run_fai_chboot_with_reboot_enabled_and_verbose_disabled_calls_wrapper_via_sudo(monkeypatch):
    monkeypatch.setenv(chboot.NFS_ROOT_ENV, "nfs://fai.example.com/srv/fai/config")
    calls = []

    def fake_runner(cmd, capture_output, text):
        calls.append(cmd)
        return FakeResult(0, stdout="switched")

    ok, output = chboot.run_fai_chboot(
        "aa:bb:cc:dd:ee:ff", "FAIBASE DEBIAN", reboot=True, verbose=False, runner=fake_runner
    )

    assert ok is True
    assert calls == [[
        "sudo", chboot.CHBOOT_WRAPPER, "approve",
        "aa:bb:cc:dd:ee:ff", "FAIBASE DEBIAN", "nfs://fai.example.com/srv/fai/config",
        "1", "0", "",
    ]]


def test_run_fai_chboot_appends_configured_boot_url(monkeypatch):
    monkeypatch.setenv(chboot.NFS_ROOT_ENV, "nfs://fai.example.com/srv/fai/config")
    monkeypatch.setenv(chboot.BOOT_URL_ENV, "http://fai.example.com/fai/")
    calls = []

    def fake_runner(cmd, capture_output, text):
        calls.append(cmd)
        return FakeResult(0, stdout="switched")

    ok, output = chboot.run_fai_chboot("aa:bb:cc:dd:ee:ff", "FAIBASE DEBIAN", runner=fake_runner)

    assert ok is True
    assert calls == [[
        "sudo", chboot.CHBOOT_WRAPPER, "approve",
        "aa:bb:cc:dd:ee:ff", "FAIBASE DEBIAN", "nfs://fai.example.com/srv/fai/config",
        "0", "1", "http://fai.example.com/fai/",
    ]]


def test_run_fai_chboot_surfaces_failure_output(monkeypatch):
    monkeypatch.setenv(chboot.NFS_ROOT_ENV, "nfs://fai.example.com/srv/fai/config")

    def fake_runner(cmd, capture_output, text):
        return FakeResult(1, stderr="fai-chboot: unknown host")

    ok, output = chboot.run_fai_chboot("aa:bb:cc:dd:ee:ff", "FAIBASE", runner=fake_runner)

    assert ok is False
    assert "unknown host" in output


def test_run_fai_chboot_rejects_invalid_mac_without_calling_runner():
    def fail_if_called(cmd, capture_output, text):
        raise AssertionError("runner should not be called for invalid mac")

    ok, output = chboot.run_fai_chboot("not-a-mac", "FAIBASE", runner=fail_if_called)

    assert ok is False
    assert "invalid mac" in output


def test_run_fai_chboot_rejects_invalid_classes_without_calling_runner():
    def fail_if_called(cmd, capture_output, text):
        raise AssertionError("runner should not be called for invalid classes")

    ok, output = chboot.run_fai_chboot("aa:bb:cc:dd:ee:ff", "bad;classes", runner=fail_if_called)

    assert ok is False
    assert "invalid classes" in output


def test_run_fai_chboot_rejects_mac_with_trailing_newline_without_calling_runner():
    def fail_if_called(cmd, capture_output, text):
        raise AssertionError("runner should not be called for mac with trailing newline")

    ok, output = chboot.run_fai_chboot("aa:bb:cc:dd:ee:ff\n", "FAIBASE", runner=fail_if_called)

    assert ok is False
    assert "invalid mac" in output


def test_run_fai_chboot_rejects_classes_with_trailing_newline_without_calling_runner():
    def fail_if_called(cmd, capture_output, text):
        raise AssertionError("runner should not be called for classes with trailing newline")

    ok, output = chboot.run_fai_chboot("aa:bb:cc:dd:ee:ff", "FAIBASE\n", runner=fail_if_called)

    assert ok is False
    assert "invalid classes" in output


def test_run_fai_chboot_discovery_success_calls_wrapper_via_sudo(monkeypatch):
    monkeypatch.setenv(chboot.NFS_ROOT_ENV, "nfs://fai.example.com/srv/fai/config")
    calls = []

    def fake_runner(cmd, capture_output, text):
        calls.append(cmd)
        return FakeResult(0, stdout="discovery mode set")

    ok, output = chboot.run_fai_chboot_discovery("aa:bb:cc:dd:ee:ff", runner=fake_runner)

    assert ok is True
    assert output == "discovery mode set"
    assert calls == [[
        "sudo", chboot.CHBOOT_WRAPPER, "discovery",
        "aa:bb:cc:dd:ee:ff", "nfs://fai.example.com/srv/fai/config", "",
    ]]


def test_run_fai_chboot_discovery_appends_configured_boot_url(monkeypatch):
    monkeypatch.setenv(chboot.NFS_ROOT_ENV, "nfs://fai.example.com/srv/fai/config")
    monkeypatch.setenv(chboot.BOOT_URL_ENV, "http://fai.example.com/fai/")
    calls = []

    def fake_runner(cmd, capture_output, text):
        calls.append(cmd)
        return FakeResult(0, stdout="discovery mode set")

    ok, output = chboot.run_fai_chboot_discovery("aa:bb:cc:dd:ee:ff", runner=fake_runner)

    assert ok is True
    assert calls == [[
        "sudo", chboot.CHBOOT_WRAPPER, "discovery",
        "aa:bb:cc:dd:ee:ff", "nfs://fai.example.com/srv/fai/config", "http://fai.example.com/fai/",
    ]]


def test_run_fai_chboot_discovery_surfaces_failure_output(monkeypatch):
    monkeypatch.setenv(chboot.NFS_ROOT_ENV, "nfs://fai.example.com/srv/fai/config")

    def fake_runner(cmd, capture_output, text):
        return FakeResult(1, stderr="fai-chboot: unknown host")

    ok, output = chboot.run_fai_chboot_discovery("aa:bb:cc:dd:ee:ff", runner=fake_runner)

    assert ok is False
    assert "unknown host" in output


def test_run_fai_chboot_discovery_rejects_invalid_mac_without_calling_runner():
    def fail_if_called(cmd, capture_output, text):
        raise AssertionError("runner should not be called for invalid mac")

    ok, output = chboot.run_fai_chboot_discovery("not-a-mac", runner=fail_if_called)

    assert ok is False
    assert "invalid mac" in output


def test_run_fai_chboot_disable_success_calls_wrapper_via_sudo():
    calls = []

    def fake_runner(cmd, capture_output, text):
        calls.append(cmd)
        return FakeResult(0, stdout="pxe config disabled")

    ok, output = chboot.run_fai_chboot_disable("aa:bb:cc:dd:ee:ff", runner=fake_runner)

    assert ok is True
    assert output == "pxe config disabled"
    assert calls == [["sudo", chboot.CHBOOT_WRAPPER, "disable", "aa:bb:cc:dd:ee:ff"]]


def test_run_fai_chboot_disable_surfaces_failure_output():
    def fake_runner(cmd, capture_output, text):
        return FakeResult(1, stderr="fai-chboot: unknown host")

    ok, output = chboot.run_fai_chboot_disable("aa:bb:cc:dd:ee:ff", runner=fake_runner)

    assert ok is False
    assert "unknown host" in output


def test_run_fai_chboot_disable_rejects_invalid_mac_without_calling_runner():
    def fail_if_called(cmd, capture_output, text):
        raise AssertionError("runner should not be called for invalid mac")

    ok, output = chboot.run_fai_chboot_disable("not-a-mac", runner=fail_if_called)

    assert ok is False
    assert "invalid mac" in output


def test_normalize_mac_lowercases_and_strips():
    assert chboot.normalize_mac(" AA:BB:CC:DD:EE:FF \n") == "aa:bb:cc:dd:ee:ff"


def test_normalize_mac_rejects_invalid_format():
    assert chboot.normalize_mac("not-a-mac") is None


def test_normalize_mac_rejects_non_string():
    assert chboot.normalize_mac(None) is None
    assert chboot.normalize_mac(123) is None


def test_normalize_mac_rejects_empty_string():
    assert chboot.normalize_mac("") is None


def test_suggest_hostname_fragment_normalizes_lowercase_and_spaces():
    assert chboot.suggest_hostname_fragment("SN 4471 XK") == "sn-4471-xk"


def test_suggest_hostname_fragment_strips_leading_and_trailing_dashes():
    assert chboot.suggest_hostname_fragment("--ABC--") == "abc"


def test_suggest_hostname_fragment_collapses_runs_of_invalid_chars():
    assert chboot.suggest_hostname_fragment("SN//4471_XK") == "sn-4471-xk"


def test_suggest_hostname_fragment_rejects_known_placeholders():
    for placeholder in [
        "Not Specified",
        "not specified",
        "Not Settable",
        "not settable",
        "To Be Filled By O.E.M.",
        "None",
        "N/A",
        "Unknown",
        "Default String",
    ]:
        assert chboot.suggest_hostname_fragment(placeholder) is None


def test_suggest_hostname_fragment_rejects_empty_or_whitespace():
    assert chboot.suggest_hostname_fragment("") is None
    assert chboot.suggest_hostname_fragment("   ") is None


def test_suggest_hostname_fragment_rejects_non_string():
    assert chboot.suggest_hostname_fragment(None) is None
    assert chboot.suggest_hostname_fragment(123) is None


def test_suggest_hostname_fragment_rejects_only_invalid_chars():
    assert chboot.suggest_hostname_fragment("!!!") is None


def test_suggest_hostname_fragment_from_uuid_uses_first_segment():
    assert (
        chboot.suggest_hostname_fragment_from_uuid("a1b2c3d4-e5f6-7890-abcd-ef1234567890")
        == "a1b2c3d4"
    )


def test_suggest_hostname_fragment_from_uuid_rejects_empty():
    assert chboot.suggest_hostname_fragment_from_uuid("") is None


def test_suggest_hostname_fragment_from_uuid_rejects_non_string():
    assert chboot.suggest_hostname_fragment_from_uuid(None) is None


def test_suggest_hostname_fragment_from_uuid_rejects_all_zero_segment():
    assert (
        chboot.suggest_hostname_fragment_from_uuid("00000000-0000-0000-0000-000000000000")
        is None
    )


def test_suggest_hostname_fragment_from_uuid_rejects_all_f_segment():
    assert (
        chboot.suggest_hostname_fragment_from_uuid("ffffffff-ffff-ffff-ffff-ffffffffffff")
        is None
    )


def test_suggest_hostname_fragment_from_uuid_rejects_all_f_segment_mixed_case():
    assert (
        chboot.suggest_hostname_fragment_from_uuid("FFFFFFFF-ffff-ffff-ffff-ffffffffffff")
        is None
    )


def test_run_fai_chboot_fails_without_nfs_root_configured(monkeypatch):
    monkeypatch.delenv(chboot.NFS_ROOT_ENV, raising=False)

    def fail_if_called(cmd, capture_output, text):
        raise AssertionError("runner should not be called without FAI_DISCOVERY_NFS_ROOT")

    ok, output = chboot.run_fai_chboot("aa:bb:cc:dd:ee:ff", "FAIBASE", runner=fail_if_called)

    assert ok is False
    assert "FAI_DISCOVERY_NFS_ROOT" in output


def test_run_fai_chboot_discovery_fails_without_nfs_root_configured(monkeypatch):
    monkeypatch.delenv(chboot.NFS_ROOT_ENV, raising=False)

    def fail_if_called(cmd, capture_output, text):
        raise AssertionError("runner should not be called without FAI_DISCOVERY_NFS_ROOT")

    ok, output = chboot.run_fai_chboot_discovery("aa:bb:cc:dd:ee:ff", runner=fail_if_called)

    assert ok is False
    assert "FAI_DISCOVERY_NFS_ROOT" in output
