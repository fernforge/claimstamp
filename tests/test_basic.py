import os
import subprocess
import sys
from pathlib import Path


def run_cli(args, cwd):
    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    return subprocess.run(
        [sys.executable, "-m", "claimstamp.cli", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        env=env,
    )


def test_run_and_verify(tmp_path):
    r = run_cli(["run", "--", "python3", "-c", "print('hi')"], cwd=tmp_path)
    assert r.returncode == 0
    assert "[claimstamp seq=1" in r.stderr
    claim_id = r.stderr.split("id=")[1].split()[0]

    v = run_cli(["verify", claim_id], cwd=tmp_path)
    assert v.returncode == 0
    assert "valid: chain intact" in v.stdout


def test_run_captures_nonzero_exit(tmp_path):
    r = run_cli(["run", "--", "python3", "-c", "import sys; sys.exit(3)"], cwd=tmp_path)
    assert r.returncode == 3
    assert "exit=3" in r.stderr


def test_audit_flags_forged_stamp(tmp_path):
    run_cli(["init"], cwd=tmp_path)
    report = tmp_path / "report.md"
    report.write_text(
        "Done. [claimstamp seq=1 id=deadbeef exit=0 ts=2026-01-01T00:00:00Z] $ pytest\n"
    )
    a = run_cli(["audit", "report.md"], cwd=tmp_path)
    assert a.returncode == 1
    assert "FORGED/MISSING" in a.stdout


def test_audit_passes_real_stamp(tmp_path):
    r = run_cli(["run", "--", "python3", "-c", "print('ok')"], cwd=tmp_path)
    claim_id = r.stderr.split("id=")[1].split()[0]
    report = tmp_path / "report.md"
    report.write_text(f"Done. {r.stderr.strip()}\n")
    a = run_cli(["audit", "report.md"], cwd=tmp_path)
    assert a.returncode == 0
    assert "1 verified" in a.stdout


def test_chain_breaks_on_tamper(tmp_path):
    r = run_cli(["run", "--", "python3", "-c", "print('a')"], cwd=tmp_path)
    claim_id = r.stderr.split("id=")[1].split()[0]

    ledger_path = tmp_path / ".claimstamp" / "ledger.jsonl"
    content = ledger_path.read_text()
    tampered = content.replace('"exit_code": 0', '"exit_code": 1', 1)
    assert tampered != content
    ledger_path.write_text(tampered)

    v = run_cli(["verify", claim_id], cwd=tmp_path)
    assert v.returncode == 2
