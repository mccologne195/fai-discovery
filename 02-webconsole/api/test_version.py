import version


def test_current_version_returns_git_describe_output():
    def fake_runner(cmd, capture_output, text, cwd):
        return FakeResult(0, stdout="v1.0.5-2-gabc1234\n")

    result = version.current_version(repo_root="/some/repo", runner=fake_runner)

    assert result == "v1.0.5-2-gabc1234"


def test_current_version_returns_none_when_git_binary_missing():
    def fake_runner(cmd, capture_output, text, cwd):
        raise FileNotFoundError("git not found")

    result = version.current_version(repo_root="/some/repo", runner=fake_runner)

    assert result is None


def test_current_version_returns_none_on_nonzero_exit():
    def fake_runner(cmd, capture_output, text, cwd):
        return FakeResult(128, stderr="fatal: not a git repository")

    result = version.current_version(repo_root="/some/repo", runner=fake_runner)

    assert result is None


def test_current_hostname_uses_injected_resolver():
    result = version.current_hostname(resolver=lambda: "fai.example.com")

    assert result == "fai.example.com"


class FakeResult:
    def __init__(self, returncode, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
