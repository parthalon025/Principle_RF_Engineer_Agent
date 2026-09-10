"""The Material / material-family controlled vocabulary (issue #404;
ADR-0015; CONTEXT.md: Material-property library, Family fallback bracket).

WHY THIS EXISTS. `designs/material_properties.py`'s `add_entry` and
`add_family_bracket` validated only that `material`/`family` were non-empty
strings -- there was no canonical list, enum, or lookup anywhere either value
was checked against. Issue #404's own bug report: "A typo when inserting a
bracket or a property silently creates an entry no lookup will ever find --
`resolve_material_property` just reports 'no_data' rather than surfacing that
the name doesn't match anything." `designs/design_families.py` already solves
exactly this problem for design families (`known_family_names`,
`get_design_family`, `is_known_design_family`, `UnknownDesignFamilyError`).
This module is the same pattern applied to materials and material families.

WHY THE TWO VOCABULARIES ARE ENFORCED DIFFERENTLY. Design families are a
small, deliberately closed set -- six of them exist, ADR-0018 is explicit
that adding a seventh is a real event, and `get_design_family` REJECTS
anything it doesn't recognise. Materials are not that kind of thing.
CONTEXT.md's Material-property library entry says so directly: "_Avoid_:
material database -- this is a growing, per-entry-provenanced knowledge
record, not a fixed reference table." A material-property library that
hard-rejected any material not already on a fixed list would defeat its own
purpose -- ADR-0015's whole point is that a human can cite a brand-new
material tomorrow and have it accumulate here permanently. So:

  * `material` (a specific named substance, e.g. "Rogers RO4350B") is an
    OPEN, growing registry. Looking up an unrecognised name never raises --
    `add_entry` (in `designs/material_properties.py`) WARNS instead
    (`UnknownMaterialNameWarning`), because the function cannot tell a
    genuinely new material apart from a typo of an existing one, and warning
    is the charter's own answer to genuine uncertainty ("warn, never
    block" -- CONTEXT.md/CLAUDE.md). The warning still names every material
    this registry already knows, so a human reading it can tell at a glance
    whether they meant an existing name.
  * `family` (a broad category used only for a Family fallback bracket, e.g.
    "generic polymer") IS the closed kind. ADR-0015 names it as exactly that
    kind of thing -- "a cited range for the material's broad family (generic
    polymer, generic conductor, etc.)" -- and its own Consequences section
    says the bracket table's actual family list is exactly what a future
    ready-for-agent ticket like this one would settle. A handful of broad
    physical categories, not a per-material catalogue, so `get_material_family`
    mirrors `get_design_family` exactly: it REJECTS a family it doesn't hold,
    naming the ones it does (`UnknownMaterialFamilyError`).

HOW THE KNOWN-MATERIAL SEED LIST WAS DERIVED, AND WHY THAT IS RECORDED. Per
`designs/design_families.py`'s own `_ALIASES` precedent: because a later
change to this list is a decision someone should be able to audit, the
initial contents are not a guess at plausible materials -- they are
harvested from the tree, and the harvest is recorded rather than left to be
re-derived by memory:

    grep -oE 'material="[^"]+"' designs/material_properties.py | sort -u

run at commit 00191f8dd5e2f99fa54efaddd92df0fd0adfcfde (`main`, "designs.
design_key uniqueness is now (design_key, revision), with collision
handling (#369) (#374)"), which yields exactly the sixteen materials in
`_HARVESTED_MATERIAL_NAMES` below -- every material already cited by
`FR4_SEED_ENTRIES`, `SUBSTRATE_SEED_ENTRIES`, and `DATASHEET_SEED_ENTRIES`.
"""

from __future__ import annotations

import warnings

# --------------------------------------------------------------------------
# Material family: closed vocabulary, mirrors designs/design_families.py
# --------------------------------------------------------------------------


class UnknownMaterialFamilyError(ValueError):
    """Raised when a caller names a material family this registry does not
    hold -- the same treatment `designs.design_families.get_design_family`
    gives an unrecognised design family."""


# ADR-0015's own two named examples ("generic polymer, generic conductor,
# etc."), plus the other broad categories this project's own material data
# already needs a fallback bracket for: a magnetic filler (mu_s > 1) changes
# an absorber's Rozanov bound (designs/design_families.py's ABSORBER
# `physical_bound.validity`); a ceramic/glass substrate
# (SUBSTRATE_SEED_ENTRIES' fused silica) is neither a polymer nor a
# conductor; an adhesive bonding layer (SUBSTRATE_SEED_ENTRIES' Rogers 2929
# Bondply, called out there as "the library's FIRST adhesive-layer
# dielectric") is its own broad category with its own typical loss.
_FAMILY_REGISTRY: dict[str, str] = {
    name.casefold(): name
    for name in (
        "generic polymer",
        "generic conductor",
        "generic dielectric",
        "generic magnetic material",
        "generic ceramic",
        "generic adhesive",
    )
}


def known_material_family_names() -> tuple[str, ...]:
    """Every registered material family name, sorted -- for error messages
    and for a caller offering a choice."""
    return tuple(sorted(_FAMILY_REGISTRY.values()))


def get_material_family(name: str) -> str:
    """Look up a material family by name, case-insensitively, returning its
    canonical spelling.

    Raises `UnknownMaterialFamilyError` naming the known families, rather
    than returning `None` or accepting the name as given -- a Family
    fallback bracket filed under a misspelled family is a bracket
    `resolve_material_property` will never find for the correctly-spelled
    family a later caller asks for (issue #404's own bug report).
    """
    if not isinstance(name, str) or not name.strip():
        raise UnknownMaterialFamilyError(
            f"family must be a non-empty string; got {name!r}. "
            f"Known material families: {', '.join(known_material_family_names())}."
        )
    canonical = _FAMILY_REGISTRY.get(name.strip().casefold())
    if canonical is None:
        raise UnknownMaterialFamilyError(
            f"Unknown material family {name!r}. Known material families: "
            f"{', '.join(known_material_family_names())}. A Family fallback "
            "bracket filed under an unrecognised family name is one "
            "resolve_material_property will never find (issue #404) -- this is "
            "a typo, or a genuinely new broad category that needs registering in "
            "designs/material_families.py, not something to guess past."
        )
    return canonical


def is_known_material_family(name: str) -> bool:
    """Non-raising form of `get_material_family`."""
    try:
        get_material_family(name)
    except UnknownMaterialFamilyError:
        return False
    return True


# --------------------------------------------------------------------------
# Material name: open, growing registry -- warns, never rejects
# --------------------------------------------------------------------------


class UnknownMaterialNameWarning(UserWarning):
    """Warned when a caller names a material this registry does not yet
    know about.

    Never raised as an error -- CONTEXT.md is explicit that the
    Material-property library is "a growing, per-entry-provenanced knowledge
    record, not a fixed reference table," so rejecting an unrecognised
    material would block a human legitimately citing a brand-new one. But an
    unrecognised name is *also* exactly what a typo of an already-known
    material looks like from this registry's point of view, and issue #404's
    bug report is precisely that such a typo "silently creates an entry no
    lookup will ever find" -- so this warns, naming every material already
    known, rather than saying nothing.
    """


_HARVESTED_MATERIAL_NAMES: tuple[str, ...] = (
    "ACI Materials SC1502 carbon",
    "ACI Materials SS1109 silver",
    "Borosilicate glass / fused silica",
    "DuPont Celanese Intexar PE874 silver",
    "DuPont Kapton HN",
    "DuPont Pyralux LF",
    "FR4",
    "Isola Astra MT77",
    "LCP (Rogers ULTRALAM 3850)",
    "PET heat-stabilised (DuPont Melinex ST505)",
    "Polyimide (DuPont Kapton 500HN)",
    "Rogers 2929 Bondply",
    "Rogers RO4003C",
    "Rogers RO4350B",
    "Silicone sheet 60 ShA (Polymax SILONA GP/FDA)",
    "TPU (solid ester-based)",
)

# Keyed case-insensitively (`str.casefold`) so "fr4" and "FR4" are the same
# registry entry; the stored value keeps the canonical display spelling.
_MATERIAL_REGISTRY: dict[str, str] = {}


def register_material(name: str) -> None:
    """Add `name` to the known-material registry.

    The explicit, deliberate action ADR-0015 already requires before a
    material enters the Material-property library at all -- "a human either
    cites/uploads a source document ... or types a bare value with a
    one-line note of where it came from." Once a name is registered here,
    `add_entry` (`designs/material_properties.py`) stops warning about it;
    a differently-spelled variant still will, which is what surfaces a typo
    against an already-cited material rather than letting it create a
    second, unreachable entry.
    """
    if not isinstance(name, str) or not name.strip():
        raise ValueError(f"material name must be a non-empty string, got {name!r}")
    resolved = name.strip()
    _MATERIAL_REGISTRY[resolved.casefold()] = resolved


def known_material_names() -> tuple[str, ...]:
    """Every registered material name, sorted -- for a warning message and
    for a caller checking what is already known before citing a new one."""
    return tuple(sorted(_MATERIAL_REGISTRY.values()))


def is_known_material(name: str) -> bool:
    """True if `name` (case-insensitively) is already registered."""
    if not isinstance(name, str):
        return False
    return name.strip().casefold() in _MATERIAL_REGISTRY


def warn_if_unknown_material(name: str) -> None:
    """Warn (`UnknownMaterialNameWarning`) if `name` is not yet registered.

    Called by `designs.material_properties.add_entry` on every new entry.
    Deliberately never raises -- see `UnknownMaterialNameWarning`'s own
    docstring for why an open registry warns instead of blocking.
    """
    if is_known_material(name):
        return
    warnings.warn(
        f"material {name!r} is not in the known Material-property library "
        f"vocabulary ({len(_MATERIAL_REGISTRY)} known: "
        f"{', '.join(known_material_names())}). This entry is NOT blocked -- "
        "CONTEXT.md's Material-property library is deliberately a growing "
        "record, not a fixed reference table -- but if this was meant to name "
        "an existing material, a typo here creates an entry no lookup will "
        "ever find (issue #404). If this is genuinely a new material, call "
        "designs.material_families.register_material(...) once the spelling "
        "is settled so future citations of it stop warning.",
        UnknownMaterialNameWarning,
        stacklevel=3,
    )


for _name in _HARVESTED_MATERIAL_NAMES:
    register_material(_name)
del _name
