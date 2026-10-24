from pathlib import Path

INSTALL_SH = Path(__file__).resolve().parents[2] / "install.sh"


def test_umask_is_confined_to_a_subshell():
    # Review 2026-10-24: "umask 077" fuer die Passwortdatei im Unattended-Modus
    # galt fuer den ganzen Rest von install.sh - danach angelegte Dateien und
    # Verzeichnisse (z.B. im NFS-exportierten Configspace, root_squash) waren nur
    # noch fuer root lesbar. umask darf nur in einer Subshell "( umask ...; ... )"
    # stehen, nie als eigene Anweisung.
    offenders = [
        f"{number}: {line.strip()}"
        for number, line in enumerate(INSTALL_SH.read_text().splitlines(), start=1)
        if line.strip().startswith("umask")
    ]

    assert offenders == []
