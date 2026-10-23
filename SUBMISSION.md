# Submission: Sealed Grant Round

## Category
Intelligent Contracts

## Contract Name
Sealed Grant Round

## Summary
A reusable GenLayer primitive for commit-reveal grant competitions: entrants commit to an entry (URL + description) via a SHA-256 digest with a bond during the commit window, reveal the content after the commit window closes, and the round settles after the scoring window to the highest-scoring revealed entry, distributing the pooled pot plus all bonds.

## What Makes This Unique
- **Cryptographic commit-reveal**: entries are committed as `sha256(f"{entry_url}|{entry_desc}")` digests; content cannot be modified between commit and reveal (hash mismatch reverts with `Commit mismatch: content changed after commit`)
- **Bounded competition windows**: commit window and scoring window are enforced with deterministic time gates; entries cannot be scored or settled outside their windows
- **Bonded competition**: entrants post a bond with commits, pooled into the pot at settlement; unresolvable rounds can be abandoned only after the scoring window closes

## How Consensus Is Used
The contract uses `gl.vm.run_nondet_unsafe()` with a custom validator for `score_entry`: each validator independently fetches the evidence URL and re-scores the revealed entry. Consensus requires exact agreement with the leader (`SCORE_TOLERANCE = 5`). Unreachable evidence deterministically scores 0.

## Technical Details
- Python-based GenLayer Intelligent Contract
- Commit digest: SHA-256 of `"{entry_url}|{entry_desc}"`; reveals verify against the committed hash
- Scoring quantized to multiples of 10 with exact consensus tolerance; settlement picks the max-score revealed entry
- TreeMap storage: rounds, commits, and per-round commit lists
- Integer-only domain (wei amounts; `bool` flags); time gates via `datetime` against consensus time
- Constants: `MAX_ROUNDS = 100`, `MAX_ENTRIES = 100`, `MAX_TITLE_CHARS = 100`, `MAX_CRITERIA_CHARS = 2000`, `MAX_DESC_CHARS = 2000`, `MAX_REASONING_CHARS = 2000`, `MAX_ENTRY_DAYS = 30`, `SCORING_WINDOW_DAYS = 3`, `SCORE_TOLERANCE = 5`

## Use Case
On-chain grant competitions where entrants must keep entries secret until the commit window closes, then compete on disclosed merit.

## Verification
- 6/6 direct-mode unit tests (commit/reveal/settle lifecycle, commit-window guard, scoring-window guard, abandon path, views)
- `genvm-lint check` + validation pass (11 methods: 2 view, 9 write)
- On-chain verified on studionet: payable creation, commit, reveal, scoring-before-commit-window revert, settlement-with-unscored-entry revert

## Live Deployment
Deployed on GenLayer studionet (chain `61999`):
[`0x4aBec31752950876B0c2dB83a152002F95d773DE`](https://explorer-studio.genlayer.com/address/0x4aBec31752950876B0c2dB83a152002F95d773DE)

## Steward Request Response
**Request**: Please correct the sealed-entry lifecycle and provide matching submitted and deployed source. During the commit window, store only a commitment digest and bond - not the plaintext entry URL or description exposed by the public getters. Bind the digest to the URL, description, and an unpredictable participant-provided salt, then allow reveal only after the commit deadline and verify those revealed values against the digest. This correction must preserve the existing scoring, settlement, and timeout-refund paths.

**Fix**: `commit_entry` now takes a participant salt and stores only the digest `sha256("{url}|{desc}|{salt}")` plus the bond (plaintext entry URL/description held out of storage and public getters until reveal); `reveal_entry` is gated to after the commit deadline and verifies the revealed values against the digest. Scoring, settlement, cancel, and abandon paths unchanged.

## Source Code
See `contracts/sealed_grant_round.py`