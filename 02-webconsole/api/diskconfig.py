"""Wählt automatisch _EFI-Varianten von disk_config-Klassen für UEFI-Zielsysteme.

Annahme: ein FAI-Profil enthält höchstens eine disk_config-tragende Klasse
(z.B. FAIBASE ODER BTRFS ODER XFS, nie mehrere kombiniert). Kombiniert ein
Profil mehrere disk_config-Klassen, von denen nur ein Teil eine _EFI-Variante
hat, kann setup-storage auf UEFI ein anderes Layout wählen als auf BIOS -
efi_classes_for() repliziert setup-storages Rückwärts-Prioritätslogik nicht,
sondern hängt _EFI-Varianten für JEDE passende Klasse an. Für die aktuell
tatsächlich genutzten Profile (immer genau eine disk_config-Klasse) ist das
unschädlich.
"""

import logging
import os

DISK_CONFIG_DIR_ENV = "FAI_DISCOVERY_DISK_CONFIG_DIR"
DEFAULT_DISK_CONFIG_DIR = "/srv/fai/config/disk_config"

logger = logging.getLogger(__name__)


def disk_config_dir():
    return os.environ.get(DISK_CONFIG_DIR_ENV, DEFAULT_DISK_CONFIG_DIR)


def efi_classes_for(classes_str):
    directory = disk_config_dir()
    tokens = classes_str.split()
    matches = []
    for token in tokens:
        candidate = f"{token}_EFI"
        if candidate in tokens:
            continue
        if os.path.isfile(os.path.join(directory, candidate)):
            matches.append(candidate)
    return matches


def classes_with_efi_variants(classes_str, firmware):
    if firmware != "uefi":
        return classes_str
    directory = disk_config_dir()
    if not os.path.isdir(directory):
        logger.warning(
            "UEFI-Zielsystem erkannt, aber disk_config-Verzeichnis %s ist nicht lesbar - "
            "_EFI-Klassen werden nicht ergaenzt, Standard-Layout wird verwendet.",
            directory,
        )
        return classes_str
    efi_classes = efi_classes_for(classes_str)
    if not efi_classes:
        return classes_str
    return classes_str + " " + " ".join(efi_classes)
