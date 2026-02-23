"""
Artifact cron worker — filesystem-based job processing.

Runs via cron every minute. Internally loops for ~65 seconds with a short
sleep, processing any queued jobs from the shared data/jobs/ directory.
PHP writes job files, this worker reads and processes them directly.

Per-key session isolation: each API key gets its own memory.sqlite
and history.jsonl in data/sessions/{key_id}/.
"""

from __future__ import annotations

import fcntl
import json
import os
import shutil
import signal
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.orchestrator import turn, TurnConfig, TurnResult
from agents.claude_client import ClaudeConfig

MAX_RUN_SECONDS = 65
IDLE_SLEEP = 0.05
POLL_SLEEP = 0.5


@dataclass
class CronConfig:
    jobs_dir: Path
    state_dir: Path
    sessions_dir: Path
    fragment_db_path: Path
    wake_context_path: Path
    ambient_path: Path
    claude_timeout: int = 90
    claude_model: str | None = None
    claude_api_key: str | None = None
    keys_db_path: Path | None = None
    verbose: bool = True


def load_config(path: Path) -> CronConfig:
    if not path.is_file():
        raise RuntimeError(f"Config not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        raw = json.load(f)

    def resolve(val: str, default: Path) -> Path:
        if not val:
            return default
        p = Path(val).expanduser()
        if not p.is_absolute():
            p = (REPO_ROOT / p).resolve()
        return p

    return CronConfig(
        jobs_dir=resolve(raw.get("jobs_dir", ""), REPO_ROOT / "data" / "jobs"),
        state_dir=resolve(raw.get("state_dir", ""), REPO_ROOT / "data" / "state"),
        sessions_dir=resolve(raw.get("sessions_dir", ""), REPO_ROOT / "data" / "sessions"),
        fragment_db_path=resolve(raw.get("fragment_db_path", ""), REPO_ROOT / "data" / "artifact.sqlite"),
        wake_context_path=resolve(
            raw.get("wake_context_path", ""),
            REPO_ROOT / "wake-context.md",
        ),
        ambient_path=resolve(raw.get("ambient_path", ""), REPO_ROOT / "ambient.md"),
        claude_timeout=int(raw.get("claude_timeout", 90)),
        claude_model=raw.get("claude_model"),
        claude_api_key=raw.get("claude_api_key"),
        keys_db_path=resolve(raw.get("keys_db_path", ""), REPO_ROOT / "data" / "keys.sqlite"),
        verbose=bool(raw.get("verbose", True)),
    )


def log(msg: str, verbose: bool = True) -> None:
    if verbose:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{ts}] {msg}", flush=True)


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")


def write_json_atomic(path: Path, data: dict) -> None:
    tmp = path.with_suffix(f".tmp.{os.getpid()}")
    encoded = json.dumps(data, indent=2, ensure_ascii=False)
    tmp.write_text(encoded + "\n", encoding="utf-8")
    os.replace(str(tmp), str(path))


def read_json_file(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except (json.JSONDecodeError, OSError):
        return None


def list_jobs(jobs_dir: Path) -> list[dict]:
    if not jobs_dir.is_dir():
        return []
    jobs = []
    for p in sorted(jobs_dir.glob("*.json")):
        if p.name.endswith(".tmp"):
            continue
        job = read_json_file(p)
        if job and "id" in job:
            jobs.append(job)
    jobs.sort(key=lambda j: j.get("created_at", ""))
    return jobs


def find_queued_job(jobs_dir: Path) -> dict | None:
    for job in list_jobs(jobs_dir):
        if job.get("status") == "queued":
            return job
    return None


def update_job(jobs_dir: Path, job_id: str, mutator) -> dict | None:
    path = jobs_dir / f"{job_id}.json"
    job = read_json_file(path)
    if job is None:
        return None
    updated = mutator(job)
    if not isinstance(updated, dict):
        return None
    updated["id"] = job_id
    updated["updated_at"] = now_iso()
    write_json_atomic(path, updated)
    return updated


def with_jobs_lock(state_dir: Path, fn):
    lock_path = state_dir / "jobs.lock"
    lock_path.touch(exist_ok=True)
    with open(lock_path, "r") as lock_fh:
        fcntl.flock(lock_fh, fcntl.LOCK_EX)
        try:
            return fn()
        finally:
            fcntl.flock(lock_fh, fcntl.LOCK_UN)


def claim_job(cfg: CronConfig, job: dict) -> dict | None:
    job_id = str(job["id"])

    def mutator(row: dict) -> dict:
        if row.get("status") != "queued":
            return row
        row["status"] = "running"
        row["claimed_at"] = now_iso()
        row["worker"] = "artifact-worker"
        return row

    def do_claim():
        return update_job(cfg.jobs_dir, job_id, mutator)

    claimed = with_jobs_lock(cfg.state_dir, do_claim)
    if claimed and claimed.get("status") == "running":
        return claimed
    return None


def complete_job(
    cfg: CronConfig,
    job_id: str,
    status: str = "done",
    display: list[dict] | None = None,
    actor: str | None = None,
    reply_text: str | None = None,
    error_message: str | None = None,
    turn_id: str | None = None,
) -> dict | None:
    def mutator(row: dict) -> dict:
        row["status"] = status
        row["completed_at"] = now_iso()
        row["reply_text"] = reply_text
        row["display"] = display or []
        row["reply_actor"] = actor or "artifact"
        row["error_message"] = error_message
        row["turn_id"] = turn_id
        return row

    return with_jobs_lock(cfg.state_dir, lambda: update_job(cfg.jobs_dir, job_id, mutator))


def ensure_session_db(cfg: CronConfig, key_id: str) -> Path:
    """Ensure per-key session directory and DB exist. Copy fragment DB on first use."""
    session_dir = cfg.sessions_dir / key_id
    session_dir.mkdir(parents=True, exist_ok=True)
    db_path = session_dir / "memory.sqlite"

    if not db_path.exists() and cfg.fragment_db_path.exists():
        # Copy the shared fragment DB as the initial memory DB
        shutil.copy2(cfg.fragment_db_path, db_path)

    return db_path


def track_usage(cfg: CronConfig, key_id: str, input_tokens: int, output_tokens: int) -> None:
    """Track token usage for a key in keys.sqlite."""
    if not cfg.keys_db_path or not cfg.keys_db_path.exists():
        return

    import sqlite3
    total = input_tokens + output_tokens
    if total <= 0:
        return

    conn = sqlite3.connect(str(cfg.keys_db_path))
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout = 5000")
        conn.execute(
            "UPDATE api_keys SET tokens_used = tokens_used + ?, last_used_at = ? WHERE id = ?",
            (total, now_iso(), key_id),
        )
        conn.commit()
    finally:
        conn.close()


def append_history(cfg: CronConfig, key_id: str, job: dict, display: list[dict], actor: str) -> None:
    """Append a completed exchange to per-key history.jsonl."""
    session_dir = cfg.sessions_dir / key_id
    session_dir.mkdir(parents=True, exist_ok=True)
    history_path = session_dir / "history.jsonl"

    entry = {
        "job_id": job.get("id"),
        "ts": now_iso(),
        "mono": {
            "actor": job.get("actor", "visitor"),
            "text": job.get("message", ""),
            "tags": job.get("tags", []),
        },
        "claude": {
            "actor": actor,
            "display": display,
        },
    }

    line = json.dumps(entry, ensure_ascii=False) + "\n"
    with history_path.open("a", encoding="utf-8") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        f.write(line)
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def update_bridge_state(cfg: CronConfig, busy: bool = False) -> None:
    state = {
        "last_seen_at": now_iso(),
        "busy": busy,
        "worker": "artifact-worker",
    }
    cfg.state_dir.mkdir(parents=True, exist_ok=True)
    write_json_atomic(cfg.state_dir / "bridge.json", state)


def check_trigger(cfg: CronConfig) -> bool:
    trigger = cfg.state_dir / "trigger"
    if trigger.exists():
        try:
            trigger.unlink()
        except OSError:
            pass
        return True
    return False


def process_job(cfg: CronConfig, job: dict) -> None:
    job_id = str(job.get("id", ""))
    if not job_id:
        raise RuntimeError("Job missing ID")

    message = str(job.get("message", ""))
    tone = str(job.get("tone", "casual"))
    key_id = str(job.get("key_id", ""))

    if not key_id:
        raise RuntimeError("Job missing key_id")

    log(f"processing {job_id} (key: {key_id[:8]}..., tone: {tone})")

    # Ensure per-key session DB
    session_db = ensure_session_db(cfg, key_id)

    # Build config for orchestrator
    cc = ClaudeConfig(timeout_seconds=cfg.claude_timeout)
    if cfg.claude_model:
        cc.model = cfg.claude_model
    if cfg.claude_api_key:
        cc.api_key = cfg.claude_api_key

    turn_config = TurnConfig(
        db_path=session_db,
        wake_context_path=cfg.wake_context_path,
        ambient_path=cfg.ambient_path,
        fragment_db_path=cfg.fragment_db_path,
        claude_config=cc,
    )

    # Run the turn
    result: TurnResult = turn(
        config=turn_config,
        message=message,
        tone=tone,
    )

    if not result.success:
        complete_job(
            cfg, job_id,
            status="error",
            error_message=result.error or "turn failed",
        )
        log(f"job {job_id} failed: {result.error}")
        return

    # Debug: show what Claude said
    raw = result.response_text
    log(f"raw response ({len(raw)} chars): {raw[:300]}{'...' if len(raw) > 300 else ''}")

    display = result.display_spans
    reply_actor = result.actor or "artifact"
    turn_id = str(result.turn)

    # Complete job FIRST (critical — the user is polling for this)
    updated = complete_job(
        cfg, job_id,
        status="done",
        display=display,
        actor=reply_actor,
        reply_text=result.response_text,
        turn_id=turn_id,
    )

    # Track usage (non-critical — log and continue if it fails)
    try:
        track_usage(cfg, key_id, result.input_tokens, result.output_tokens)
        log(f"tokens: {result.input_tokens} in + {result.output_tokens} out = {result.input_tokens + result.output_tokens}")
    except Exception as e:
        log(f"warning: track_usage failed for {job_id}: {e}")

    # Append to per-key history (non-critical — log and continue if it fails)
    if updated:
        try:
            append_history(cfg, key_id, updated, display, reply_actor)
        except Exception as e:
            log(f"warning: append_history failed for {job_id}: {e}")

    log(f"job {job_id} done (turn {result.turn}, {len(display)} display spans)")


def cleanup_old_jobs(jobs_dir: Path, max_age_seconds: int = 300) -> int:
    now = time.time()
    deleted = 0
    for path in jobs_dir.glob("*.json"):
        if path.name.endswith(".tmp"):
            continue
        try:
            data = read_json_file(path)
            if data and data.get("status") in ("done", "error"):
                if now - path.stat().st_mtime > max_age_seconds:
                    path.unlink(missing_ok=True)
                    deleted += 1
        except Exception:
            pass
    return deleted


def run(cfg: CronConfig) -> int:
    log("artifact worker starting")
    log(f"jobs_dir: {cfg.jobs_dir}")
    log(f"fragments: {cfg.fragment_db_path}")

    cfg.state_dir.mkdir(parents=True, exist_ok=True)
    lock_path = cfg.state_dir / "artifact-worker.lock"
    lock_fd = open(lock_path, "a")
    try:
        fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (OSError, IOError):
        lock_fd.close()
        log("another worker is already running, exiting")
        return 0

    shutdown = False

    def handle_signal(signum, frame):
        nonlocal shutdown
        shutdown = True
        log(f"received signal {signum}, finishing current work...")

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    start = time.monotonic()
    last_cleanup = 0.0

    try:
        while not shutdown:
            elapsed = time.monotonic() - start
            if elapsed >= MAX_RUN_SECONDS:
                log("time limit reached, exiting")
                break

            now_mono = time.monotonic()
            if now_mono - last_cleanup >= 60:
                n = cleanup_old_jobs(cfg.jobs_dir)
                if n:
                    log(f"cleaned up {n} old job files")
                last_cleanup = now_mono

            update_bridge_state(cfg, busy=False)

            triggered = check_trigger(cfg)

            queued = find_queued_job(cfg.jobs_dir)
            if queued is None:
                time.sleep(IDLE_SLEEP if triggered else POLL_SLEEP)
                continue

            claimed = claim_job(cfg, queued)
            if claimed is None:
                continue

            update_bridge_state(cfg, busy=True)
            try:
                process_job(cfg, claimed)
            except Exception as e:
                job_id = str(claimed.get("id", ""))
                log(f"job {job_id} error: {e}")
                if job_id:
                    try:
                        complete_job(
                            cfg, job_id,
                            status="error",
                            error_message="An internal error occurred. Please try again.",
                        )
                    except Exception as ce:
                        log(f"failed to report error: {ce}")
            finally:
                update_bridge_state(cfg, busy=False)

    finally:
        try:
            update_bridge_state(cfg, busy=False)
        except Exception:
            pass
        fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
        lock_fd.close()
        log("worker exiting")

    return 0


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="artifact cron worker")
    parser.add_argument(
        "--config",
        default=str(REPO_ROOT / "worker" / "config.json"),
        help="Path to worker config JSON",
    )
    args = parser.parse_args()

    cfg = load_config(Path(args.config).expanduser().resolve())
    return run(cfg)


if __name__ == "__main__":
    raise SystemExit(main())
