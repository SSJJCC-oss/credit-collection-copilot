"""store.py - the copilot's OWN database: reminder drafts, order reviews and the audit log.

The billing database is never written to. Everything the copilot needs to remember
(what it recommended, what people approved, every tool call) lives here instead.
"""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from copilot.config import load_settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS reminder_drafts (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id    INTEGER NOT NULL,
    customer_name  TEXT    NOT NULL,
    language       TEXT    NOT NULL CHECK (language IN ('en', 'ar')),
    channel        TEXT    NOT NULL CHECK (channel IN ('email', 'sms')),
    recipient      TEXT,
    subject        TEXT    NOT NULL,
    body           TEXT    NOT NULL,
    invoice_refs   TEXT    NOT NULL,
    amount_due     REAL    NOT NULL,
    status         TEXT    NOT NULL DEFAULT 'draft'
                   CHECK (status IN ('draft', 'approved', 'rejected', 'logged', 'sent')),
    created_at     TEXT    NOT NULL,
    decided_by     TEXT,
    decided_at     TEXT,
    decision_note  TEXT
);

CREATE TABLE IF NOT EXISTS order_reviews (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    order_no        TEXT    NOT NULL,
    customer_id     INTEGER NOT NULL,
    recommendation  TEXT    NOT NULL CHECK (recommendation IN ('APPROVE', 'REVIEW', 'HOLD')),
    reasons         TEXT    NOT NULL,
    rules_version   TEXT    NOT NULL,
    as_of           TEXT    NOT NULL,
    created_at      TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    at           TEXT    NOT NULL,
    actor        TEXT    NOT NULL,
    action       TEXT    NOT NULL,
    arguments    TEXT,
    result       TEXT,
    ok           INTEGER NOT NULL,
    duration_ms  INTEGER
);
"""


def now_utc() -> str:
    """The current time in UTC as text, e.g. '2026-11-12T10:30:00+00:00'."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect_store(path: Path | None = None) -> sqlite3.Connection:
    """Open the copilot's own database (read-write), creating it and its tables if needed."""
    path = path or load_settings().copilot_db
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def save_order_review(con: sqlite3.Connection, review: dict, as_of: str, rules_version: str) -> int:
    """Record a recommendation made by credit_rules.review_order(). Returns the new row id."""
    with con:
        cursor = con.execute("""
            INSERT INTO order_reviews (order_no, customer_id, recommendation, reasons,
                                       rules_version, as_of, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (review["order_no"], review["customer_id"], review["decision"],
             json.dumps(review["reasons"]), rules_version, as_of, now_utc()))
    return cursor.lastrowid


def log_event(con: sqlite3.Connection, actor: str, action: str, arguments: dict | None = None,
              result: str = "", ok: bool = True, duration_ms: int | None = None) -> int:
    """Write one line to the audit log: who did what, with which inputs, and how it went."""
    with con:
        cursor = con.execute("""
            INSERT INTO audit_log (at, actor, action, arguments, result, ok, duration_ms)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (now_utc(), actor, action, json.dumps(arguments or {}), result[:500], int(ok), duration_ms))
    return cursor.lastrowid


def recent_audit(con: sqlite3.Connection, limit: int = 20) -> list[dict]:
    """The most recent audit-log entries, newest first."""
    rows = con.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]

# ---------------------------------------------------------------- reminder drafts (step 4.3)

def _draft_from_row(row: sqlite3.Row) -> dict:
    """Turn a reminder_drafts row into a dictionary, with invoice_refs back as a list."""
    draft = dict(row)
    draft["invoice_refs"] = json.loads(draft["invoice_refs"])
    return draft


def create_draft(con: sqlite3.Connection, contact: dict, reminder: dict, language: str,
                 channel: str, recipient: str | None, created_by: str = "copilot") -> dict:
    """Save a reminder as a DRAFT waiting for a person to approve it. Nothing is sent."""
    with con:
        cursor = con.execute("""
            INSERT INTO reminder_drafts (customer_id, customer_name, language, channel, recipient,
                                         subject, body, invoice_refs, amount_due, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (contact["customer_id"], contact["customer_name"], language, channel, recipient,
             reminder["subject"], reminder["body"], json.dumps(reminder["invoice_refs"]),
             reminder["amount_due"], now_utc()))
    log_event(con, created_by, "create_draft",
              {"customer_id": contact["customer_id"], "language": language, "channel": channel},
              f"draft {cursor.lastrowid}: {reminder['amount_due']:,.2f} due")
    return get_draft(con, cursor.lastrowid)


def get_draft(con: sqlite3.Connection, draft_id: int) -> dict:
    """One reminder draft by its id."""
    row = con.execute("SELECT * FROM reminder_drafts WHERE id = ?", (draft_id,)).fetchone()
    if row is None:
        raise ValueError(f"Draft {draft_id} not found")
    return _draft_from_row(row)


def list_drafts(con: sqlite3.Connection, status: str | None = None) -> list[dict]:
    """All drafts (newest first), or only those with the given status, e.g. 'draft'."""
    if status:
        rows = con.execute("SELECT * FROM reminder_drafts WHERE status = ? ORDER BY id DESC",
                           (status,)).fetchall()
    else:
        rows = con.execute("SELECT * FROM reminder_drafts ORDER BY id DESC").fetchall()
    return [_draft_from_row(r) for r in rows]


def decide_draft(con: sqlite3.Connection, draft_id: int, approve: bool, decided_by: str,
                 dry_run: bool, note: str = "") -> dict:
    """A PERSON approves or rejects a draft. Approved + DRY_RUN -> 'logged' (never sent)."""
    if not decided_by.strip():
        raise ValueError("A decision must record the name of the person making it")
    draft = get_draft(con, draft_id)
    if draft["status"] != "draft":
        raise ValueError(f"Draft {draft_id} was already decided (status: {draft['status']})")

    if not approve:
        new_status = "rejected"
    elif dry_run:
        new_status = "logged"        # demo mode: recorded as if sent, but nothing leaves the computer
    else:
        new_status = "approved"      # ready for a real email/SMS sender (not part of this project)

    with con:
        con.execute("""
            UPDATE reminder_drafts
            SET status = ?, decided_by = ?, decided_at = ?, decision_note = ?
            WHERE id = ?""", (new_status, decided_by, now_utc(), note, draft_id))
    log_event(con, decided_by, "approve_draft" if approve else "reject_draft",
              {"draft_id": draft_id, "dry_run": dry_run}, new_status)
    return get_draft(con, draft_id)