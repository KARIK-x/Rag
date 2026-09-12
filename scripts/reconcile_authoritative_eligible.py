"""
Authoritative eligible-set reconciliation.
READ-ONLY against /Users/ashim/locus_drive/locus_drive.db.
Produces deterministic machine-readable reconciliation.
No modifications to authoritative catalog.
"""
import sqlite3, json, sys
DB = "/Users/ashim/locus_drive/locus_drive.db"

SUPPORTED = {
    "application/pdf",
    "application/rtf",
    "application/json",
    "text/plain", "text/markdown", "text/csv", "text/tab-separated-values",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel", "application/msword",
    "application/vnd.oasis.opendocument.text", "application/vnd.oasis.opendocument.spreadsheet",
}
WORKSPACE = {
    "application/vnd.google-apps.document",
    "application/vnd.google-apps.spreadsheet",
    "application/vnd.google-apps.presentation",
    "application/vnd.google-apps.form",
    "application/vnd.google-apps.drawing",
    "application/vnd.google-apps.script",
}
SUPPORTED |= WORKSPACE
EXCLUDED_PREFIXES = ("image/", "video/", "audio/", "font/", "application/photoshop", "application/illustrator", "application/x-executable", "application/x-msdownload")

def is_eligible(mime_type: str) -> bool:
    if mime_type.startswith(EXCLUDED_PREFIXES):
        return False
    return mime_type in SUPPORTED

conn = sqlite3.connect(DB)
cur = conn.cursor()
cur.execute("SELECT DISTINCT id, name, mime_type FROM files WHERE trashed = 0")
rows = cur.fetchall()
conn.close()

eligible_ids = set()
excluded_by_category = {"image/video/audio/font/design/executable/other": set()}
for row in rows:
    rid, rname, rmime = row
    if is_eligible(rmime):
        eligible_ids.add(rid)
    else:
        excluded_by_category.setdefault("other", set()).add((rid, rname, rmime))

reconciliation = {
    "authoritative_catalog_total": len({r[0] for r in rows}),
    "eligible_ids_count": len(eligible_ids),
    "eligible_ids_file_exists": False,
    "excluded_other_example_ids": list({k[0] for k in excluded_by_category.get("other", set())})[:5] if excluded_by_category.get("other") else [],
}

# Save eligible IDs list (machine-readable, deterministic)
with open("data/audit/eligible_authoritative_ids.json", "w", encoding="utf-8") as f:
    f.write(json.dumps(sorted(eligible_ids), indent=2, ensure_ascii=False))
reconciliation["eligible_ids_file_exists"] = True
reconciliation["eligible_set_path"] = "data/audit/eligible_authoritative_ids.json"
print(json.dumps(reconciliation, indent=2, ensure_ascii=False))
