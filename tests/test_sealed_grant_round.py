"""Direct-mode tests for the SealedGrantRound contract (commit-reveal grants)."""

import hashlib
import json
import re
from datetime import datetime, timedelta

from gltest.direct import create_address

TITLE = "Open Source Weather Station"
CRITERIA = "Must be open hardware, publish schematics, and report data via API."
ENTRY_URL = "https://github.com/example/weather-station"
ENTRY_DESC = "ESP32 weather station with open schematics and REST API"
ENTRY_BODY = "Open schematics and API docs. SEALED_BODY_MARKER"
SALT = "steward-salt-9f8e7d6c5b4a"

SCORE_80_JSON = json.dumps({"score": 77, "reasoning": "Strong but missing enclosure docs."})


def _create_round(contract, vm, creator, pot=1000, min_bond=10, entry_days=1):
    vm.sender = creator
    vm.value = pot
    return contract.create_round(
        title=TITLE, criteria=CRITERIA, min_bond=min_bond, entry_days=entry_days,
    )


def _commit(contract, vm, participant, round_id, url=ENTRY_URL, desc=ENTRY_DESC, bond=10, salt=SALT):
    vm.sender = participant
    vm.value = bond
    digest = hashlib.sha256(f"{url}|{desc}|{salt}".encode()).hexdigest()
    return contract.commit_entry(
        round_id=round_id, commit_hash=digest, bond=bond,
    )


def _reveal(contract, vm, participant, round_id, url=ENTRY_URL, desc=ENTRY_DESC, salt=SALT):
    vm.sender = participant
    return contract.reveal_entry(
        round_id=round_id, entry_url=url, entry_desc=desc, salt=salt,
    )


def _score(contract, vm, round_id, entry_id, url=ENTRY_URL, body=ENTRY_BODY, llm_json=SCORE_80_JSON):
    vm.mock_web(re.escape(url), {"status": 200, "body": body})
    vm.mock_llm(
        r"BEGIN UNTRUSTED ENTRY DESCRIPTION ---[\s\S]*" + re.escape(ENTRY_DESC)
        + r"[\s\S]*--- BEGIN FETCHED CONTENT ---\s*" + re.escape(body),
        llm_json,
    )
    return contract.score_entry(round_id=round_id, entry_id=entry_id)


def test_create_round_validates(direct_vm, direct_deploy):
    contract = direct_deploy("contracts/sealed_grant_round.py")
    creator = create_address("creator")

    direct_vm.sender = creator
    direct_vm.value = 1000
    with direct_vm.expect_revert("Title and criteria are required"):
        contract.create_round("", "criteria", 10, 1)
    with direct_vm.expect_revert("Title too long"):
        contract.create_round("x" * 101, "criteria", 10, 1)
    with direct_vm.expect_revert("Pot must be > 0"):
        direct_vm.value = 0
        contract.create_round("T", "c", 10, 1)
    direct_vm.value = 1000
    with direct_vm.expect_revert("Entry window cannot exceed 30 days"):
        contract.create_round("T", "c", 10, 31)

    rid = _create_round(contract, direct_vm, creator)
    r = contract.get_round(rid)
    assert r["status"] == "open"
    assert r["commit_deadline"] > r["created_at"]
    assert r["score_deadline"] > r["commit_deadline"]


def test_commit_guards(direct_vm, direct_deploy):
    contract = direct_deploy("contracts/sealed_grant_round.py")
    creator = create_address("creator")
    alice = create_address("alice")

    rid = _create_round(contract, direct_vm, creator)

    with direct_vm.expect_revert("Round not found"):
        _commit(contract, direct_vm, alice, "nope")
    with direct_vm.expect_revert("Bond below minimum"):
        _commit(contract, direct_vm, alice, rid, bond=5)
    with direct_vm.expect_revert("Commit window has closed"):
        direct_vm.warp((datetime.now() + timedelta(days=2)).isoformat())
        _commit(contract, direct_vm, alice, rid)
    direct_vm.warp((datetime.now() - timedelta(days=2)).isoformat())
    eid = _commit(contract, direct_vm, alice, rid)
    assert contract.get_commit(eid)["entry_url"] == ""
    assert contract.get_commit(eid)["entry_desc"] == ""
    with direct_vm.expect_revert("Already committed to this round"):
        _commit(contract, direct_vm, alice, rid)


def test_reveal_guards_and_commit_mismatch(direct_vm, direct_deploy):
    contract = direct_deploy("contracts/sealed_grant_round.py")
    creator = create_address("creator")
    alice = create_address("alice")

    rid = _create_round(contract, direct_vm, creator)
    eid = _commit(contract, direct_vm, alice, rid, bond=10)

    with direct_vm.expect_revert("Commit window has not closed"):
        _reveal(contract, direct_vm, alice, rid, url=ENTRY_URL, desc=ENTRY_DESC, salt=SALT)

    direct_vm.warp((datetime.now() + timedelta(days=2)).isoformat())
    with direct_vm.expect_revert("No committed entry for sender"):
        _reveal(contract, direct_vm, create_address("mallory"), rid, url=ENTRY_URL, desc=ENTRY_DESC, salt=SALT)
    with direct_vm.expect_revert("Commit mismatch: content changed after commit"):
        _reveal(contract, direct_vm, alice, rid, url=ENTRY_URL, desc="totally different desc", salt=SALT)

    _reveal(contract, direct_vm, alice, rid, url=ENTRY_URL, desc=ENTRY_DESC, salt=SALT)
    with direct_vm.expect_revert("Entry already revealed"):
        _reveal(contract, direct_vm, alice, rid, url=ENTRY_URL, desc=ENTRY_DESC, salt=SALT)
    assert contract.get_commit(eid)["revealed"] is True
    assert contract.get_commit(eid)["entry_url"] == ENTRY_URL


def test_score_flow_quantize_and_settle(direct_vm, direct_deploy):
    contract = direct_deploy("contracts/sealed_grant_round.py")
    creator = create_address("creator")
    alice = create_address("alice")

    rid = _create_round(contract, direct_vm, creator, pot=1000, min_bond=10)
    eid = _commit(contract, direct_vm, alice, rid, bond=10)

    with direct_vm.expect_revert("Commit window has not closed"):
        _score(contract, direct_vm, rid, eid)

    direct_vm.warp((datetime.now() + timedelta(days=2)).isoformat())
    _reveal(contract, direct_vm, alice, rid, url=ENTRY_URL, desc=ENTRY_DESC, salt=SALT)
    result = _score(contract, direct_vm, rid, eid)
    assert result["score"] == 80
    assert contract.get_commit(eid)["scored"] is True

    with direct_vm.expect_revert("Entry already scored"):
        _score(contract, direct_vm, rid, eid)

    direct_vm.warp((datetime.now() + timedelta(days=5)).isoformat())
    result = contract.settle_round(round_id=rid)
    assert result["winner"] == str(alice)
    assert result["payout"] == 1010
    assert contract.get_round(rid)["status"] == "settled"


def test_abandon_after_score_deadline_refunds(direct_vm, direct_deploy):
    contract = direct_deploy("contracts/sealed_grant_round.py")
    creator = create_address("creator")
    alice = create_address("alice")

    rid = _create_round(contract, direct_vm, creator, pot=1000, min_bond=10)
    eid = _commit(contract, direct_vm, alice, rid, bond=10)
    direct_vm.warp((datetime.now() + timedelta(days=2)).isoformat())
    _reveal(contract, direct_vm, alice, rid, url=ENTRY_URL, desc=ENTRY_DESC, salt=SALT)
    direct_vm.warp((datetime.now() + timedelta(days=5)).isoformat())
    contract.abandon_round(round_id=rid)
    assert contract.get_round(rid)["status"] == "abandoned"


def test_cancel_only_creator_and_only_empty(direct_vm, direct_deploy):
    contract = direct_deploy("contracts/sealed_grant_round.py")
    creator = create_address("creator")
    alice = create_address("alice")

    rid = _create_round(contract, direct_vm, creator, pot=1000, min_bond=10)
    _commit(contract, direct_vm, alice, rid, bond=10)
    direct_vm.sender = creator
    with direct_vm.expect_revert("Round has entries; cannot cancel"):
        contract.cancel_round(round_id=rid)

    empty = _create_round(contract, direct_vm, creator, pot=1000, min_bond=10)
    contract.cancel_round(round_id=empty)
    assert contract.get_round(empty)["status"] == "cancelled"
