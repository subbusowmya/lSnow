"""
migrate_from_supabase.py  (v2 - merges hardcoded + Supabase)

The original index.html had 60 incidents hardcoded directly in its JS source
(INC-001 to INC-060). Supabase only ever received a subset of those (whatever
got edited/re-saved live through the app) - not a fresh set of new incidents.
This script merges both sources correctly:

  1. Start from hardcoded_incidents.json (the original 60, extracted from
     index.html's source) - the authoritative base snapshot.
  2. Overlay any live Supabase rows on top, matching by id - Supabase's
     version wins where both exist, since it reflects later edits/notes.
  3. Write the merged result into incidents.db.

Usage (from C:\\sqlite\\lSnow, with hardcoded_incidents.json in the same folder):
    python migrate_from_supabase.py
"""

import json
import os
import sqlite3
import urllib.request

SB_URL = "https://hjvwmlzvbehitumvrbrx.supabase.co"
SB_KEY = "sb_publishable_4TozzH5Vrpk-fbi8SUoK-w_3XcDGOK_"

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "incidents.db")
HARDCODED_PATH = os.path.join(HERE, "hardcoded_incidents.json")


def fetch_supabase_incidents():
    """Paginate with Range headers so a project-level 'Max Rows' cap can't
    silently truncate results."""
    all_rows = []
    page_size = 20
    offset = 0
    while True:
        url = f"{SB_URL}/rest/v1/incidents?select=*&order=date.desc"
        req = urllib.request.Request(
            url,
            headers={
                "apikey": SB_KEY,
                "Authorization": f"Bearer {SB_KEY}",
                "Range-Unit": "items",
                "Range": f"{offset}-{offset + page_size - 1}",
            },
        )
        with urllib.request.urlopen(req) as resp:
            batch = json.loads(resp.read().decode("utf-8"))
        if not batch:
            break
        all_rows.extend(batch)
        print(f"  fetched rows {offset}-{offset + len(batch) - 1} ({len(batch)} rows)")
        if len(batch) < page_size:
            break
        offset += page_size
    return all_rows


def main():
    if not os.path.exists(HARDCODED_PATH):
        raise SystemExit(
            f"Could not find hardcoded_incidents.json at {HARDCODED_PATH}. "
            f"Make sure it's in the same folder as this script."
        )

    with open(HARDCODED_PATH, "r", encoding="utf-8") as f:
        hardcoded = json.load(f)
    print(f"Loaded {len(hardcoded)} hardcoded incidents from index.html source.")

    print("Fetching live incidents from Supabase...")
    sb_rows = fetch_supabase_incidents()
    print(f"Fetched {len(sb_rows)} incidents from Supabase.")

    # Merge: hardcoded is the base, Supabase overrides matching ids
    merged = {r["id"]: r for r in hardcoded}
    for r in sb_rows:
        wn = r.get("worknotes")
        if isinstance(wn, str):
            try:
                r["worknotes"] = json.loads(wn or "[]")
            except json.JSONDecodeError:
                r["worknotes"] = []
        merged[r["id"]] = {**merged.get(r["id"], {}), **r}

    final_rows = list(merged.values())
    print(f"Merged total: {len(final_rows)} unique incidents.")

    if os.path.exists(DB_PATH):
        backup = DB_PATH + ".bak"
        os.replace(DB_PATH, backup)
        print(f"Existing incidents.db backed up to {backup}")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
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

    for r in final_rows:
        cur.execute(
            """INSERT INTO incidents
               (id, title, category, priority, status, assignee, client, module, date, desc, worknotes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                r.get("id"), r.get("title"), r.get("category"), r.get("priority"),
                r.get("status"), r.get("assignee"), r.get("client"), r.get("module"),
                r.get("date"), r.get("desc"), json.dumps(r.get("worknotes") or []),
            ),
        )

    conn.commit()
    conn.close()
    print(f"Wrote {len(final_rows)} incidents into {DB_PATH}")
    print("Next: run server.py, then open index.html through it (see instructions).")


if __name__ == "__main__":
    main()
