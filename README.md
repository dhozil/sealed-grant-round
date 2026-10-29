<div align="center">

# Sealed Grant Round

**Commit-reveal grant competition: entrants commit to entries with SHA-256 digests and bonds, then compete on revealed merit with LLM-scored consensus.

![GenLayer](https://img.shields.io/badge/GenLayer-Intelligent%20Contract-6a4cff)
![Python](https://img.shields.io/badge/Python-3.12-3776AB)
![Status](https://img.shields.io/badge/status-live%20on%20studionet-2ea44f)
![Tests](https://img.shields.io/badge/tests-6%20passed-2ea44f)

[Live Contract](https://explorer-studio.genlayer.com/address/0x4DFF08D3b454b01E65B2BF3fFB348c936F2E483f) 

[GenLayer Docs](https://docs.genlayer.com)

</div>

---

## Why

Grant competitions are vulnerable to front-running: entrants who see each other's proposals before committing can tailor entries to the judges. SealedGrantRound makes entries cryptographically sealed during the commit phase (SHA-256 of `"{url}|{desc}"` + bond), then runs an LLM-scored competition after the commit window closes.

## Live Deployment

| | |
|---|---|
| **Contract** | [SealedGrantRound](https://explorer-studio.genlayer.com/address/0x4DFF08D3b454b01E65B2BF3fFB348c936F2E483f) |
| **Address** | `0x4DFF08D3b454b01E65B2BF3fFB348c936F2E483f` |
| **Network** | GenLayer studionet (chain `61999`) |
| **Status** | Deployed + verified on-chain |

## Highlights

- **Commit-reveal sealing**: commit accepts a participant-generated commitment digest (`sha256("{url}|{desc}|{salt}")`) plus bond and stores **digest + bond only** (no plaintext URL/desc/salt); reveal after the commit deadline verifies the revealed values against the stored digest
- **Bounded windows**: commit window and scoring window enforced by deterministic time gates; settlement only after all entries revealed + scored
- **Bonded pot**: entrant bonds pool into the pot at settlement; unresolvable rounds abandonable only after scoring window closes

## How It Works

```
create_round (payable pot, entry_days -> commit_deadline, score_deadline = commit + 3d)
      |
      v
commit_entry (entrant: entry URL + desc + bond, within commit window)
      |
      v  (after commit_deadline)
reveal_entry (entry ID + content -> hash check)
      |
      v  (after score_deadline, within scoring window)
score_entry (LLM consensus on revealed entry)
      |
      v
settle_round (argmax score -> pay pot + bonds)
```

## Methods

| Role | Method | Guard |
|---|---|---|
| Anyone | `create_round`, `commit_entry` | payable; bounded inputs; commit window |
| Any | `reveal_entry` | hash match; commit window passed |
| Any | `score_entry` | status open; windows; consensus |
| Anyone | `settle_round`, `cancel_round`, `abandon_round` | window/state guards |
| Any | `get_round`, `get_all_rounds`, `get_round_commits`, `get_commit` | read-only |

## Security Model

- Commit-reveal prevents front-running and content tampering between commit and reveal
- Time gates make scoring/settlement ungameable outside their windows; abandon path refund-safe after scoring window
- LLM scoring unreachable -> deterministic score 0; exact-consensus scoring (`SCORE_TOLERANCE = 5`)

## Test

```bash
gltest tests/ -q   # 6 passed
```

## Lint

```bash
genvm-lint check contracts/sealed_grant_round.py
```

## Live Deployment

Deployed on GenLayer studionet (chain `61999`):
[`0x4DFF08D3b454b01E65B2BF3fFB348c936F2E483f`](https://explorer-studio.genlayer.com/address/0x4DFF08D3b454b01E65B2BF3fFB348c936F2E483f)