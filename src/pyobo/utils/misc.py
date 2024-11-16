"""Miscellaneous utilities."""

import logging
from datetime import datetime

__all__ = [
    "cleanup_version",
]

logger = logging.getLogger(__name__)

BIZARRE_LOGGED = set()


def cleanup_version(data_version: str, prefix: str) -> str | None:
    """Clean the version information."""
    if data_version.endswith(".owl"):
        data_version = data_version[: -len(".owl")]
    if data_version.endswith(prefix):
        data_version = data_version[: -len(prefix)]
    if data_version.startswith("releases/"):
        data_version = data_version[len("releases/") :]
    if prefix == "orth":
        # TODO add bioversions for this
        return "2"

    version_prefixes = [
        "http://www.orpha.net/version",
        "https://www.orphadata.com/data/ontologies/ordo/last_version/ORDO_en_",
        "http://humanbehaviourchange.org/ontology/bcio.owl/",
        "http://purl.org/pav/",
        "http://identifiers.org/combine.specifications/teddy.rel-",
    ]
    for version_prefix in version_prefixes:
        if data_version.startswith(version_prefix):
            return data_version[len(version_prefix) :]

    version_prefixes_split = [
        "http://www.ebi.ac.uk/efo/releases/v",
        "http://www.ebi.ac.uk/swo/swo.owl/",
        "http://semanticscience.org/ontology/sio/v",
        "http://ontology.neuinfo.org/NIF/ttl/nif/version/",
    ]
    for version_prefix_split in version_prefixes_split:
        if data_version.startswith(version_prefix_split):
            return data_version[len(version_prefix_split) :].split("/")[0]

    if data_version.replace(".", "").isnumeric():
        return data_version  # consecutive, major.minor, or semantic versioning
    for v in reversed(data_version.split("/")):
        v = v.strip()
        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            continue
        else:
            return v
    if (prefix, data_version) not in BIZARRE_LOGGED:
        logger.debug("[%s] bizarre version: %s", prefix, data_version)
        BIZARRE_LOGGED.add((prefix, data_version))
    return data_version
