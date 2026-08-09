from __future__ import annotations

import argparse
import calendar
import re
import subprocess
import sys
import time
from pathlib import Path

from .ledger import Ledger, find_ledger_dir

STAMP_RE = re.compile(
    r"\[claimstamp\s+seq=(?P<seq>\d+)\s+id=(?P<id>[0-9a-f]{6,64})\s+"
    r"exit=(?P<exit>-?\d+)\s+ts=(?P<ts>[0-9T:Z\-]+)\]"
)


def format_stamp(entry: dict) -> str:
    return (
        f"[claimstamp seq={entry['seq']} id={entry['id']} "
        f"exit={entry['exit_code']} ts={entry['timestamp']}] $ {entry['command']}"
    )


def cmd_init(args: argparse.Namespace) -> int:
    ledger = Ledger.open()
    ledger.ensure_initialized()
    print(f"initialized ledger at {ledger.path}")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    command = args.command
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        print("claimstamp run: no command given", file=sys.stderr)
        return 2

    ledger = Ledger.open()
    start = time.time()
    proc = subprocess.run(command, capture_output=True)
    duration = time.time() - start

    sys.stdout.buffer.write(proc.stdout)
    sys.stderr.buffer.write(proc.stderr)

    entry = ledger.append_run(
        command=" ".join(command),
        exit_code=proc.returncode,
        duration_s=duration,
        stdout=proc.stdout,
        stderr=proc.stderr,
    )
    print(format_stamp(entry.__dict__), file=sys.stderr)
    return proc.returncode


def cmd_verify(args: argparse.Namespace) -> int:
    ledger = Ledger.open()
    entry = ledger.find_by_id(args.claim_id)
    if entry is None:
        print(f"no such claim: {args.claim_id}", file=sys.stderr)
        return 1
    ok, checked = ledger.verify_chain(upto_id=args.claim_id)
    if not ok:
        print(f"CHAIN BROKEN before entry {args.claim_id} (checked {checked} entries)")
        return 2
    print(f"valid: chain intact through seq={entry['seq']} ({checked} entries checked)")
    print(f"  command: {entry['command']}")
    print(f"  exit_code: {entry['exit_code']}")
    print(f"  timestamp: {entry['timestamp']}")
    print(f"  cwd: {entry['cwd']}")
    return 0


def cmd_ledger(args: argparse.Namespace) -> int:
    ledger = Ledger.open()
    entries = ledger.all_entries()
    if not entries:
        print("(empty ledger)")
        return 0
    for e in entries:
        print(format_stamp(e))
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    text = Path(args.file).read_text(encoding="utf-8")
    stamps = list(STAMP_RE.finditer(text))
    if not stamps:
        print(f"no claimstamp stamps found in {args.file}")
        return 0 if not args.require else 1

    ledger = Ledger.open()
    ok_count = 0
    problems = []
    now = time.time()

    for m in stamps:
        claim_id = m.group("id")
        claimed_exit = int(m.group("exit"))
        entry = ledger.find_by_id(claim_id)
        if entry is None:
            problems.append(f"FORGED/MISSING: id={claim_id} has no matching ledger entry")
            continue
        chain_ok, _ = ledger.verify_chain(upto_id=claim_id)
        if not chain_ok:
            problems.append(f"TAMPERED: id={claim_id} ledger chain invalid up to this entry")
            continue
        if entry["exit_code"] != claimed_exit:
            problems.append(
                f"MISMATCH: id={claim_id} text claims exit={claimed_exit}, "
                f"ledger recorded exit={entry['exit_code']}"
            )
            continue
        entry_time = time.strptime(entry["timestamp"], "%Y-%m-%dT%H:%M:%SZ")
        age_s = now - calendar.timegm(entry_time)
        if args.max_age is not None and age_s > args.max_age:
            problems.append(
                f"STALE: id={claim_id} is {int(age_s)}s old, older than --max-age {args.max_age}s"
            )
            continue
        ok_count += 1

    print(f"{args.file}: {len(stamps)} stamp(s) found, {ok_count} verified, {len(problems)} problem(s)")
    for p in problems:
        print(f"  - {p}")
    return 0 if not problems else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="claimstamp",
        description="Ground an agent's claims in commands it actually ran.",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("init", help="initialize a ledger in the current directory tree")
    sp.set_defaults(func=cmd_init)

    sp = sub.add_parser(
        "run",
        help="run a command, record a tamper-evident stamp of what happened",
    )
    sp.add_argument("command", nargs=argparse.REMAINDER)
    sp.set_defaults(func=cmd_run)

    sp = sub.add_parser("verify", help="verify a claim id against the ledger's hash chain")
    sp.add_argument("claim_id")
    sp.set_defaults(func=cmd_verify)

    sp = sub.add_parser("ledger", help="print all recorded entries")
    sp.set_defaults(func=cmd_ledger)

    sp = sub.add_parser(
        "audit",
        help="scan a text file for [claimstamp ...] stamps and check each against the ledger",
    )
    sp.add_argument("file")
    sp.add_argument(
        "--max-age",
        type=int,
        default=None,
        help="flag stamps older than this many seconds as stale",
    )
    sp.add_argument(
        "--require",
        action="store_true",
        help="exit nonzero if the file contains no stamps at all",
    )
    sp.set_defaults(func=cmd_audit)

    return p


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
