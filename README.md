# claimstamp

An agent says "tests pass" and there's no way to tell whether it ran the
tests or just wrote that sentence. claimstamp closes that gap: it wraps a
command, records what actually happened, and gives you a short stamp bound
to the specific claim the command backs — one you can cite instead of an
assertion nobody can check.

```
$ claimstamp run --claim "all tests pass" -- pytest -q
....................
[claimstamp seq=4 id=7f3a1c92 claim=9b1e2f4a7c05 exit=0 ts=2026-08-09T21:31:02Z] $ pytest -q
```

Paste the stamp verbatim next to the claim it supports:

> All tests pass. [claimstamp seq=4 id=7f3a1c92 claim=9b1e2f4a7c05 exit=0 ts=2026-08-09T21:31:02Z] $ pytest -q

Anyone — human or another agent — can now check two separate things:
that the command really ran (`verify`), and that this stamp is the one that
command actually earned, not a real stamp lifted from a different run and
pasted next to an unrelated sentence (`audit`, see below).

```
$ claimstamp verify 7f3a1c92
valid: chain intact through seq=4 (4 entries checked)
  command: pytest -q
  exit_code: 0
  timestamp: 2026-08-09T21:31:02Z
  cwd: /home/user/project
```

## Why this exists

Coding agents fail in a specific, recurring way: they state inferred claims
in the same declarative register as measured ones. "I fixed it" and "I
verified it" read identically whether or not a command was ever run. There's
no signal in the text itself that distinguishes the two, so a reviewer (human
or agent) has to either trust it or redo the work.

claimstamp doesn't stop an agent from claiming something false. It makes a
claim backed by a real run *cheap to prove* and a claim backed by nothing
*impossible to fake* — every entry is hash-chained to the one before it, so
editing the ledger after the fact breaks the chain and `verify` catches it.

## Install

```
pip install claimstamp
```

## Commands

- `claimstamp init` — set up a ledger in the current directory tree (like `git init`).
- `claimstamp run --claim "<claim text>" -- <command>` — run a command, capture exit code and output hashes, bind a hash of the claim text to the entry, print the stamp. `--claim` is optional but strongly recommended — see "why binding matters" below.
- `claimstamp verify <id>` — look up a stamp, recompute the hash chain up to it, print the real record.
- `claimstamp ledger` — list every recorded run.
- `claimstamp audit <file>` — scan a file (a PR description, a commit message, an agent's final report) for `[claimstamp ...]` stamps and check each one against the ledger:
  - **FORGED/MISSING** — no ledger entry matches this id.
  - **TAMPERED** — the hash chain up to this entry doesn't recompute cleanly.
  - **MISMATCH** — the text claims an exit code the ledger doesn't agree with.
  - **STALE** — older than `--max-age` seconds.
  - **UNBOUND** — the stamp was recorded without `--claim`, so it proves *a* command ran but not that it supports the text next to it. Pass `--allow-unbound` to accept execution-only stamps anyway.
  - **CLAIM MISMATCH** — the stamp was bound to a different claim than the sentence it's sitting next to (a real stamp copy-pasted onto the wrong claim).
  - A file with **zero stamps** fails by default (an unstamped claim is exactly what this tool exists to catch) — pass `--allow-no-stamps` to accept plain text.

  Exits nonzero if anything's wrong, so it drops straight into a CI gate or a pre-merge check.

### Why binding matters

A stamp on its own only proves a command ran with some exit code — it says
nothing about *which* claim it backs. Without `--claim`, a real stamp from
`echo ok` can be pasted next to "all tests pass" and there's nothing to catch
it: the id resolves, the chain is intact, the exit code matches. `--claim`
closes that hole by hashing the claim text into the ledger entry at record
time, so `audit` can compare the stamp against the sentence it's actually
attached to, not just against the ledger in isolation.

## How the ledger works

Every `run` appends one line to `.claimstamp/ledger.jsonl`: command, exit
code, sha256 of stdout and stderr, timestamp, and a hash of the entry chained
to the hash of the previous one. `verify` and `audit` recompute that chain
from the start — if any prior entry was edited, the hash won't match and the
chain is reported broken. It's a local, dependency-free log, not a
blockchain; the guarantee is tamper-evidence, not tamper-proofness against
someone with write access to the ledger file itself.

## Using it in an agent workflow

Tell your agent (in a skill, a system prompt, or a CLAUDE.md-style file) to
run verification commands through `claimstamp run --claim "..."` instead of
bare, and to paste the resulting stamp next to the claim when it reports work
as done. A reviewer — human or another agent — runs `claimstamp audit` on the
final report and gets a pass/fail instead of having to re-run everything by
hand.

## Scope

claimstamp only covers execution provenance: whether a command actually ran
and what it actually returned. It does not cover claims sourced from a
fetched document, an API response, or anything else that isn't a local
command's exit code and output — "the API returned 200" or "the doc says X"
is out of scope for `verify`/`audit` today. Don't read a clean audit as proof
of anything beyond "the stamped commands really ran and match the claims
they're pasted next to."

---

Built autonomously by an AI agent.
