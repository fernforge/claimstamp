# claimstamp

An agent says "tests pass" and there's no way to tell whether it ran the
tests or just wrote that sentence. claimstamp closes that gap: it wraps a
command, records what actually happened, and gives you a short stamp you can
cite instead of an assertion nobody can check.

```
$ claimstamp run -- pytest -q
....................
[claimstamp seq=4 id=7f3a1c92 exit=0 ts=2026-08-09T21:31:02Z] $ pytest -q
```

Now the claim isn't "tests pass" — it's "tests pass, id=7f3a1c92", and anyone
(including another agent) can check it:

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
- `claimstamp run -- <command>` — run a command, capture exit code and output hashes, append a chained entry, print the stamp.
- `claimstamp verify <id>` — look up a stamp, recompute the hash chain up to it, print the real record.
- `claimstamp ledger` — list every recorded run.
- `claimstamp audit <file>` — scan a file (a PR description, a commit message, an agent's final report) for `[claimstamp ...]` stamps and check each one against the ledger. Flags stamps that don't match any entry, entries whose recorded exit code doesn't match what the text claims, or stamps older than `--max-age` seconds. Exits nonzero if anything's wrong, so it drops straight into a CI gate or a pre-merge check.

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
run verification commands through `claimstamp run --` instead of bare, and to
cite the resulting stamp when it reports a claim as done. A reviewer — human
or another agent — runs `claimstamp audit` on the final report and gets a
pass/fail instead of having to re-run everything by hand.

---

Built autonomously by an AI agent.
