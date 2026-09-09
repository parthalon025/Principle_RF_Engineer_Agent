"""Tests for knowledge/ink_lookup.py (issue #326).

Pure-function tests -- `search_ink_product` takes `search_digikey`/
`search_mouser` as injectable seams (mirroring `knowledge.digikey.
search_digikey_product`'s own `get_token`/`search` injection), so no
ALLOW_EXTERNAL_NETWORK_TOOLS/DATABASE_URL/real network access is needed
here. `tests/test_digikey.py`/`tests/test_mouser.py` already cover each
provider's own search-and-parse logic against a recorded-shape API
response; this file only covers the fallback/combination logic that sits
above them.
"""

from knowledge.ink_lookup import search_ink_product


def _ok(distributor: str, mpn: str = "8331-14G") -> dict:
    return {
        "status": "ok",
        "distributor": distributor,
        "manufacturer": "MG Chemicals",
        "manufacturer_part_number": mpn,
        "datasheet_url": f"https://example.com/{mpn}.pdf",
    }


def _no_match(distributor: str, query: str) -> dict:
    return {"status": "no_match", "distributor": distributor, "queried": query}


def _no_datasheet(distributor: str) -> dict:
    return {
        "status": "no_datasheet",
        "distributor": distributor,
        "manufacturer": "MG Chemicals",
        "manufacturer_part_number": "8331-14G",
    }


def test_digikey_match_is_returned_without_querying_mouser():
    calls: list[str] = []

    def fake_digikey(query: str) -> dict:
        calls.append("digikey")
        return _ok("digikey")

    def fake_mouser(query: str) -> dict:
        calls.append("mouser")
        raise AssertionError("mouser should not be queried when digikey already matched")

    result = search_ink_product(
        "conductive silver ink", search_digikey=fake_digikey, search_mouser=fake_mouser
    )

    assert result["status"] == "ok"
    assert result["distributor"] == "digikey"
    assert result["manufacturer_part_number"] == "8331-14G"
    assert result["datasheet_url"] == "https://example.com/8331-14G.pdf"
    assert calls == ["digikey"]


def test_falls_back_to_mouser_when_digikey_has_no_match():
    result = search_ink_product(
        "conductive silver ink",
        search_digikey=lambda query: _no_match("digikey", query),
        search_mouser=lambda query: _ok("mouser", mpn="842AR"),
    )

    assert result["status"] == "ok"
    assert result["distributor"] == "mouser"
    assert result["manufacturer_part_number"] == "842AR"


def test_falls_back_to_mouser_when_digikey_match_has_no_datasheet():
    """A product with no citable datasheet is not a usable citation --
    check the other distributor for one before giving up."""
    result = search_ink_product(
        "conductive silver ink",
        search_digikey=lambda query: _no_datasheet("digikey"),
        search_mouser=lambda query: _ok("mouser"),
    )

    assert result["status"] == "ok"
    assert result["distributor"] == "mouser"


def test_no_match_from_either_distributor_returns_clear_nothing_found_result():
    result = search_ink_product(
        "an ink nobody sells",
        search_digikey=lambda query: _no_match("digikey", query),
        search_mouser=lambda query: _no_match("mouser", query),
    )

    assert result == {
        "status": "no_match",
        "queried": "an ink nobody sells",
        "checked": ["digikey", "mouser"],
    }


def test_no_datasheet_from_both_distributors_is_reported_as_no_match():
    """Neither distributor offers a citable datasheet -- this is "nothing
    found" from the caller's point of view (issue #326 acceptance criterion
    2: never a guessed or approximated value), not a partial success."""
    result = search_ink_product(
        "conductive silver ink",
        search_digikey=lambda query: _no_datasheet("digikey"),
        search_mouser=lambda query: _no_datasheet("mouser"),
    )

    assert result["status"] == "no_match"
    assert result["checked"] == ["digikey", "mouser"]


def test_never_returns_a_bare_numeric_property():
    """issue #326: the tool returns a matched product + datasheet link,
    never an extracted numeric property -- there is no key in either
    outcome shape that could carry one."""
    ok_result = search_ink_product(
        "conductive silver ink",
        search_digikey=lambda query: _ok("digikey"),
        search_mouser=lambda query: _fail_if_called(),
    )
    allowed_ok_keys = {
        "status",
        "distributor",
        "manufacturer",
        "manufacturer_part_number",
        "datasheet_url",
    }
    assert set(ok_result.keys()) <= allowed_ok_keys

    no_match_result = search_ink_product(
        "nothing",
        search_digikey=lambda query: _no_match("digikey", query),
        search_mouser=lambda query: _no_match("mouser", query),
    )
    assert set(no_match_result.keys()) == {"status", "queried", "checked"}


def _fail_if_called():
    raise AssertionError("mouser should not be queried when digikey already matched")
