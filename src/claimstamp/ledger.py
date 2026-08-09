"""Append-only, hash-chained ledger of executed commands.

Each entry records what was actually run, its exit code, and hashes of its
output, chained to the previous entry so the file can't be edited after the
fact without breaking the chain. This is the thing an agent points to when it
claims "tests pass" or "the fix works" instead of just asserting it.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

LEDGER_DIRNAME = ".claimstamp"
LEDGER_FILENAME = "ledger.jsonl"
GENESIS_HASH = "0" * 64


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_text(text: str) -> str:
    return _sha256_bytes(text.encode("utf-8"))


def normalize_claim(text: str) -> str:
    """Collapse whitespace and strip surrounding punctuation/markup so the same
    claim sentence hashes the same whether it's typed at `run --claim` time or
    lifted verbatim into a report next to the stamp."""
    return " ".join(text.strip().strip("-*>#. \t\"'").split()).lower()


def claim_hash(text: str) -> str:
    normalized = normalize_claim(text)
    return _sha256_text(normalized)[:12] if normalized else ""


def find_ledger_dir(start: Optional[Path] = None) -> Path:
    """Walk up from `start` (default cwd) looking for an existing .claimstamp dir.

    Falls back to `<cwd>/.claimstamp` if none is found (caller creates it).
    """
    cur = (start or Path.cwd()).resolve()
    for candidate in [cur, *cur.parents]:
        d = candidate / LEDGER_DIRNAME
        if d.is_dir():
            return d
    return (start or Path.cwd()).resolve() / LEDGER_DIRNAME


@dataclass
class Entry:
    seq: int
    timestamp: str
    cwd: str
    command: str
    exit_code: int
    duration_s: float
    stdout_sha256: str
    stderr_sha256: str
    stdout_bytes: int
    stderr_bytes: int
    prev_hash: str
    claim: str = ""
    claim_hash: str = ""
    id: str = ""
    hash: str = ""

    def canonical(self) -> str:
        body = {k: v for k, v in asdict(self).items() if k not in ("hash", "id")}
        return json.dumps(body, sort_keys=True, separators=(",", ":"))


class Ledger:
    def __init__(self, path: Path):
        self.path = path

    @classmethod
    def open(cls, start: Optional[Path] = None) -> "Ledger":
        d = find_ledger_dir(start)
        return cls(d / LEDGER_FILENAME)

    def ensure_initialized(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.touch()

    def _read_entries(self) -> list[dict]:
        if not self.path.exists():
            return []
        entries = []
        with self.path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
        return entries

    def last_hash(self) -> str:
        entries = self._read_entries()
        if not entries:
            return GENESIS_HASH
        return entries[-1]["hash"]

    def append_run(
        self,
        command: str,
        exit_code: int,
        duration_s: float,
        stdout: bytes,
        stderr: bytes,
        claim: str = "",
        cwd: Optional[str] = None,
    ) -> Entry:
        self.ensure_initialized()
        entries = self._read_entries()
        seq = len(entries) + 1
        prev_hash = entries[-1]["hash"] if entries else GENESIS_HASH
        normalized_claim = normalize_claim(claim) if claim else ""
        entry = Entry(
            seq=seq,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            cwd=cwd or str(Path.cwd()),
            command=command,
            exit_code=exit_code,
            duration_s=round(duration_s, 3),
            stdout_sha256=_sha256_bytes(stdout),
            stderr_sha256=_sha256_bytes(stderr),
            stdout_bytes=len(stdout),
            stderr_bytes=len(stderr),
            prev_hash=prev_hash,
            claim=normalized_claim,
            claim_hash=claim_hash(claim) if claim else "",
        )
        entry.hash = _sha256_text(entry.canonical())
        entry.id = entry.hash[:8]
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(entry), sort_keys=True) + "\n")
        return entry

    def find_by_id(self, claim_id: str) -> Optional[dict]:
        for e in self._read_entries():
            if e["id"] == claim_id or e["hash"].startswith(claim_id):
                return e
        return None

    def verify_chain(self, upto_id: Optional[str] = None) -> tuple[bool, int]:
        """Recompute the hash chain from genesis. Returns (ok, entries_checked)."""
        entries = self._read_entries()
        prev = GENESIS_HASH
        checked = 0
        for e in entries:
            body = {k: v for k, v in e.items() if k not in ("hash", "id")}
            expected = _sha256_text(json.dumps(body, sort_keys=True, separators=(",", ":")))
            if expected != e["hash"] or e["prev_hash"] != prev:
                return False, checked
            prev = e["hash"]
            checked += 1
            if upto_id and (e["id"] == upto_id or e["hash"].startswith(upto_id)):
                return True, checked
        if upto_id:
            return False, checked
        return True, checked

    def all_entries(self) -> list[dict]:
        return self._read_entries()
