"""Data structures for OBO."""

from __future__ import annotations

from typing import Any

import bioregistry
import curies
from curies import ReferenceTuple
from curies.api import ExpansionError
from pydantic import Field, field_validator, model_validator

from .utils import obo_escape
from ..constants import GLOBAL_CHECK_IDS
from ..identifier_utils import normalize_curie

__all__ = [
    "Reference",
    "Referenced",
]


class Reference(curies.Reference):
    """A namespace, identifier, and label."""

    name: str | None = Field(default=None, description="the name of the reference")

    @field_validator("prefix")
    def validate_prefix(cls, v):  # noqa
        """Validate the prefix for this reference."""
        norm_prefix = bioregistry.normalize_prefix(v)
        if norm_prefix is None:
            raise ExpansionError(f"Unknown prefix: {v}")
        return norm_prefix

    @property
    def preferred_prefix(self) -> str:
        """Get the preferred curie for this reference."""
        return bioregistry.get_preferred_prefix(self.prefix) or self.prefix

    @property
    def preferred_curie(self) -> str:
        """Get the preferred curie for this reference."""
        return f"{self.preferred_prefix}:{self.identifier}"

    @model_validator(mode="before")
    def validate_identifier(cls, values):  # noqa
        """Validate the identifier."""
        prefix, identifier = values.get("prefix"), values.get("identifier")
        if not prefix or not identifier:
            return values
        resource = bioregistry.get_resource(prefix)
        if resource is None:
            raise ExpansionError(f"Unknown prefix: {prefix}")
        values["prefix"] = resource.prefix
        values["identifier"] = resource.standardize_identifier(identifier)
        if GLOBAL_CHECK_IDS and not resource.is_valid_identifier(values["identifier"]):
            raise ValueError(f"non-standard identifier: {resource.prefix}:{values['identifier']}")
        return values

    @classmethod
    def auto(cls, prefix: str, identifier: str) -> Reference:
        """Create a reference and autopopulate its name."""
        from ..api import get_name

        name = get_name(prefix, identifier)
        return cls.model_validate({"prefix": prefix, "identifier": identifier, "name": name})

    @property
    def bioregistry_link(self) -> str:
        """Get the bioregistry link."""
        return f"https://bioregistry.io/{self.curie}"

    @classmethod
    def from_curie(  # type:ignore[override]
        cls,
        curie: str,
        name: str | None = None,
        *,
        strict: bool = True,
        auto: bool = False,
        ontology_prefix: str | None = None,
        node: Reference | None = None,
    ) -> Reference | None:
        """Get a reference from a CURIE.

        :param curie: The compact URI (CURIE) to parse in the form of `<prefix>:<identifier>`
        :param name: The name associated with the CURIE
        :param strict: If true, raises an error if the CURIE can not be parsed.
        :param auto: Automatically look up name
        """
        prefix, identifier = normalize_curie(
            curie, strict=strict, ontology_prefix=ontology_prefix, node=node
        )
        return cls._materialize(prefix=prefix, identifier=identifier, name=name, auto=auto)

    @classmethod
    def from_iri(
        cls,
        iri: str,
        name: str | None = None,
        *,
        auto: bool = False,
    ) -> Reference | None:
        """Get a reference from an IRI using the Bioregistry.

        :param iri: The IRI to parse
        :param name: The name associated with the CURIE
        :param auto: Automatically look up name
        """
        prefix, identifier = bioregistry.parse_iri(iri)
        return cls._materialize(prefix=prefix, identifier=identifier, name=name, auto=auto)

    @classmethod
    def _materialize(
        cls,
        prefix: str | None,
        identifier: str | None,
        name: str | None = None,
        *,
        auto: bool = False,
    ) -> Reference | None:
        if prefix is None or identifier is None:
            return None
        if name is None and auto:
            return cls.auto(prefix=prefix, identifier=identifier)
        return cls.model_validate({"prefix": prefix, "identifier": identifier, "name": name})

    @property
    def _escaped_identifier(self):
        return obo_escape(self.identifier)

    def __str__(self):
        identifier_lower = self.identifier.lower()
        if identifier_lower.startswith(f"{self.prefix.lower()}:"):
            rv = identifier_lower
        else:
            rv = f"{self.preferred_prefix}:{self._escaped_identifier}"
        if self.name:
            rv = f"{rv} ! {self.name}"
        return rv


class Referenced:
    """A class that contains a reference."""

    reference: Reference

    def __hash__(self) -> int:
        return self.reference.__hash__()

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, curies.Reference | Referenced):
            return self.prefix == other.prefix and self.identifier == other.identifier
        raise TypeError

    def __lt__(self, other: Referenced) -> bool:
        if not isinstance(other, curies.Reference | Referenced):
            raise TypeError
        return self.reference < other.reference

    @property
    def prefix(self):
        """The prefix of the typedef."""
        return self.reference.prefix

    @property
    def name(self):
        """The name of the typedef."""
        return self.reference.name

    @property
    def identifier(self) -> str:
        """The local unique identifier for this typedef."""
        return self.reference.identifier

    @property
    def curie(self) -> str:
        """The CURIE for this typedef."""
        return self.reference.curie

    @property
    def preferred_curie(self) -> str:
        """The preferred CURIE for this typedef."""
        return self.reference.preferred_curie

    @property
    def pair(self) -> ReferenceTuple:
        """The pair of namespace/identifier."""
        return self.reference.pair

    @property
    def bioregistry_link(self) -> str:
        """Get the bioregistry link."""
        return self.reference.bioregistry_link
