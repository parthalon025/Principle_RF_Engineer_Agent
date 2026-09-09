"""Ink/adhesive lookup: a citation-only, search-across-distributors tool for
an unresolved ink-related Capability warning (issue #326; #315's parent
spec; `docs/manufacturing-equipment-api-research.md`'s "wire the citation-
only version for the ink/adhesive half" recommendation).

`CONTEXT.md`'s **Capability warning** entry: when a design candidate is a
good fit but the currently selected **Ink-property library** entry does not
meet a stated need (e.g. "needs volume resistivity below X; the loaded ink
is Y"), the candidate stays `kept` and carries the warning rather than being
dropped -- the shop's ink on hand is expected to change. This module is the
tool a systems engineer (or the design loop, on their behalf) reaches for
once that warning names a gap: search Digi-Key's and Mouser's free product-
search APIs (`knowledge.digikey.search_digikey_product`/`knowledge.mouser.
search_mouser_product` -- both already confirmed free-tier and viable for
ink/adhesive SKUs specifically, per the research doc above) for a real,
purchasable product, and hand back its name and datasheet link for a human
to read and, if they choose, cite when they add a new Ink-property library
row themselves.

**Never writes anything.** Like `knowledge.sourcing.arxiv.search_arxiv_papers`
before it, this module calls neither `ingest_document` nor any Ink-property-
library write -- `search_digikey_product`/`search_mouser_product` have no
code path that could call either (see their own docstrings), and this
module adds none of its own. A found product is a citation, not a value:
the same "the library itself never parses a document; an uploaded document
is the citation/audit trail, not an extraction target" rule `CONTEXT.md`
already states for the Material-property library applies unchanged here --
this tool never even downloads the datasheet PDF, let alone reads a number
out of it.

`query` is a free-text product description, the same shape `search_arxiv_
papers`' own `query` parameter takes for a literature search -- assembled by
whoever is resolving the Capability warning (the design loop's systems
role, or a human) from the warning's own `family`/`capability_property`/
`reason` fields (e.g. a warning naming a `volume_resistivity_ohm_m` gap
might become the query "conductive silver ink"). This module does not
parse a Capability warning entry itself: CONTEXT.md's Capability warning
shape is `value`/`comparator`/`unit` plus free text, not a distributor
search keyword, and inventing a fixed mapping from one to the other would
be exactly the kind of un-asked-for abstraction this ticket does not need.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from knowledge.digikey import search_digikey_product
from knowledge.mouser import search_mouser_product

SearchDigikeyFn = Callable[[str], dict[str, Any]]
SearchMouserFn = Callable[[str], dict[str, Any]]

_CHECKED = ["digikey", "mouser"]


def search_ink_product(
    query: str,
    *,
    search_digikey: SearchDigikeyFn = search_digikey_product,
    search_mouser: SearchMouserFn = search_mouser_product,
) -> dict[str, Any]:
    """Search Digi-Key first, then Mouser, for a real, purchasable product
    matching `query`, and return the first one that comes back with a
    citable datasheet.

    Digi-Key is queried first, unconditionally; Mouser is queried only if
    Digi-Key did not itself return a usable citation (`search_digikey`
    returned anything other than `"ok"` -- `"no_match"` or
    `"no_datasheet"`, `knowledge.digikey.search_digikey_product`'s own two
    non-`"ok"` statuses) -- issue #326 acceptance criterion 1's "queries at
    least one of the two confirmed-free APIs," with the second queried only
    when the first alone would not already answer the question.

    Returns one of two shapes:
      - `{"status": "ok", "distributor": "digikey" | "mouser",
        "manufacturer": ..., "manufacturer_part_number": ...,
        "datasheet_url": ...}` -- a real, purchasable product with a
        citable datasheet.
      - `{"status": "no_match", "queried": query, "checked": ["digikey",
        "mouser"]}` -- a clear "nothing found" result, issue #326
        acceptance criterion 2, returned whenever neither distributor
        offers a usable citation (no product matched at all, or a matched
        product with no datasheet on file) -- never a guessed or
        approximated value.

    Each provider's own `require_external_network_tools_enabled` gate
    (`knowledge.sourcing_common`) still applies -- calling this with
    ALLOW_EXTERNAL_NETWORK_TOOLS unset raises the same
    `ExternalNetworkToolsDisabledError` `search_digikey_product`/
    `search_mouser_product` raise on their own, the instant Digi-Key would
    be queried.
    """
    digikey_result = search_digikey(query)
    if digikey_result.get("status") == "ok":
        return _citation(digikey_result)

    mouser_result = search_mouser(query)
    if mouser_result.get("status") == "ok":
        return _citation(mouser_result)

    return {"status": "no_match", "queried": query, "checked": list(_CHECKED)}


def _citation(result: dict[str, Any]) -> dict[str, Any]:
    """Narrow a `search_digikey_product`/`search_mouser_product` `"ok"`
    result down to exactly the citation fields this tool ever hands back --
    product identity and its datasheet link, never a numeric property."""
    return {
        "status": "ok",
        "distributor": result["distributor"],
        "manufacturer": result["manufacturer"],
        "manufacturer_part_number": result["manufacturer_part_number"],
        "datasheet_url": result["datasheet_url"],
    }
