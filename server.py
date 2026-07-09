"""
server.py

Self-hosted replacement for Supabase. Serves index.html AND owns incidents.db
directly. Run this on the shared/always-on machine; everyone (you, your
manager, etc.) points their browser at http://<that-machine>:5000

Requires: pip install flask --break-system-packages   (if not already installed)

Usage:
    python server.py
Then open:
    http://localhost:5000            (on the server machine itself)
    http://<server-ip>:5000           (from any other PC on the network)
"""

import json
import os
import sqlite3
from flask import Flask, request, jsonify, send_from_directory

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "incidents.db")

app = Flask(__name__, static_folder=HERE)


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create the table if incidents.db doesn't exist yet (fresh install)."""
    if os.path.exists(DB_PATH):
        return
    conn = get_conn()
    conn.execute("""
        CREATE TABLE incidents (
            id       TEXT PRIMARY KEY,
            title    TEXT,
            category TEXT,
            priority TEXT,
            status   TEXT,
            assignee TEXT,
            client   TEXT,
            module   TEXT,
            date     TEXT,
            desc     TEXT,
            worknotes TEXT
        )
    """)
    conn.commit()
    conn.close()
    print(f"Created fresh {DB_PATH}. If you meant to migrate existing data, "
          f"run migrate_from_supabase.py first instead of starting fresh.")


def row_to_dict(row):
    d = dict(row)
    try:
        d["worknotes"] = json.loads(d.get("worknotes") or "[]")
    except (json.JSONDecodeError, TypeError):
        d["worknotes"] = []
    return d


# ── Static file (the app itself) ──────────────────────────────
@app.route("/")
def index():
    return send_from_directory(HERE, "index.html")


# ── API ────────────────────────────────────────────────────────
@app.route("/api/incidents", methods=["GET"])
def list_incidents():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM incidents ORDER BY date DESC").fetchall()
    conn.close()
    return jsonify([row_to_dict(r) for r in rows])


@app.route("/api/incidents", methods=["POST"])
def create_incident():
    inc = request.get_json(force=True)
    conn = get_conn()
    conn.execute(
        """INSERT INTO incidents (id, title, category, priority, status, assignee, client, module, date, desc, worknotes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(id) DO UPDATE SET
             title=excluded.title, category=excluded.category, priority=excluded.priority,
             status=excluded.status, assignee=excluded.assignee, client=excluded.client,
             module=excluded.module, date=excluded.date, desc=excluded.desc, worknotes=excluded.worknotes
        """,
        (
            inc.get("id"), inc.get("title"), inc.get("category"), inc.get("priority"),
            inc.get("status"), inc.get("assignee"), inc.get("client"), inc.get("module"),
            inc.get("date"), inc.get("desc"), json.dumps(inc.get("worknotes") or []),
        ),
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True}), 201


@app.route("/api/incidents/<incident_id>", methods=["PUT", "PATCH"])
def update_incident(incident_id):
    inc = request.get_json(force=True)
    conn = get_conn()
    conn.execute(
        """UPDATE incidents SET
             title=?, category=?, priority=?, status=?, assignee=?, client=?,
             module=?, date=?, desc=?, worknotes=?
           WHERE id=?""",
        (
            inc.get("title"), inc.get("category"), inc.get("priority"), inc.get("status"),
            inc.get("assignee"), inc.get("client"), inc.get("module"), inc.get("date"),
            inc.get("desc"), json.dumps(inc.get("worknotes") or []), incident_id,
        ),
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/incidents/<incident_id>", methods=["DELETE"])
def delete_incident(incident_id):
    conn = get_conn()
    conn.execute("DELETE FROM incidents WHERE id=?", (incident_id,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=False)
