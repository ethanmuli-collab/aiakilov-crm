"""Local SQLite data layer (demo mode).

The CRM ships with a self-contained SQLite database seeded from
`data/synthetic_leads.csv`, so the demo runs with zero external configuration.
Table names mirror the Supabase schema (`aiakilov_*`) one-to-one, so switching
`supabase_service` in as the backing store is a drop-in change.
"""

from __future__ import annotations

import os
import sqlite3
import uuid
from datetime import date, datetime, timedelta, timezone

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(BASE_DIR, "data", "aiakilov.db")
CSV_PATH = os.path.join(BASE_DIR, "data", "synthetic_leads.csv")

LEAD_STATUSES = [
    "New", "Contacted", "Interested", "Follow-up",
    "Counseling", "Offer Sent", "Won", "Lost",
]
STATUS_HE = {
    "New": "חדש", "Contacted": "נוצר קשר", "Interested": "מתעניין",
    "Follow-up": "מעקב", "Counseling": "ייעוץ", "Offer Sent": "נשלחה הצעה",
    "Won": "נסגר בהצלחה", "Lost": "אבוד",
}
LEAD_SOURCES = [
    "Facebook", "Instagram", "Google Ads", "Website",
    "Referral", "Organic", "WhatsApp", "Event",
]
SOURCE_HE = {
    "Facebook": "פייסבוק", "Instagram": "אינסטגרם", "Google Ads": "גוגל אדס",
    "Website": "אתר", "Referral": "המלצה", "Organic": "אורגני",
    "WhatsApp": "וואטסאפ", "Event": "אירוע",
}
PAYMENT_STATUSES = ["pending", "paid", "failed", "refunded"]
PAYMENT_HE = {"pending": "ממתין", "paid": "שולם", "failed": "נכשל", "refunded": "זוכה"}

COURSES_SEED = [
    ("Python for AI", "יסודות Python לפיתוח מערכות בינה מלאכותית", 3900, "ד\"ר עמית רון", 40, 60, "מתחילים"),
    ("Machine Learning", "אלגוריתמים, אימון מודלים והערכת ביצועים", 6400, "ד\"ר שירה בן דוד", 30, 90, "מתקדמים"),
    ("AI Automation", "אוטומציה עסקית מבוססת AI ואינטגרציות", 4500, "יונתן אלמוג", 45, 50, "בינוני"),
    ("Prompt Engineering", "הנדסת פרומפטים למודלי שפה גדולים", 2900, "מאיה קדם", 60, 30, "מתחילים"),
    ("AI Agents", "בניית סוכנים אוטונומיים וכלים מבוססי LLM", 5800, "אורי לביא", 25, 70, "מתקדמים"),
    ("Data Science", "ניתוח נתונים, סטטיסטיקה וויזואליזציה", 7200, "ד\"ר נועה שגב", 35, 100, "מתקדמים"),
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS aiakilov_profiles (
    id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, full_name TEXT NOT NULL,
    role TEXT NOT NULL, created_at TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS aiakilov_courses (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT, price REAL NOT NULL,
    start_date TEXT, end_date TEXT, lecturer TEXT, capacity INTEGER, hours INTEGER,
    difficulty TEXT, status TEXT DEFAULT 'active', created_at TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS aiakilov_leads (
    id TEXT PRIMARY KEY, first_name TEXT NOT NULL, last_name TEXT NOT NULL,
    email TEXT, phone TEXT, age INTEGER, city TEXT, occupation TEXT, education TEXT,
    course_interest TEXT, lead_source TEXT, status TEXT DEFAULT 'New', budget REAL,
    preferred_schedule TEXT, previous_ai_experience INTEGER DEFAULT 0,
    interaction_count INTEGER DEFAULT 0, assigned_sales_rep TEXT, notes TEXT,
    purchased INTEGER DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS aiakilov_lead_activities (
    id TEXT PRIMARY KEY, lead_id TEXT NOT NULL, activity_type TEXT NOT NULL,
    description TEXT, created_by TEXT, created_at TEXT NOT NULL,
    FOREIGN KEY (lead_id) REFERENCES aiakilov_leads(id));

CREATE TABLE IF NOT EXISTS aiakilov_followups (
    id TEXT PRIMARY KEY, lead_id TEXT NOT NULL, title TEXT NOT NULL, due_date TEXT,
    done INTEGER DEFAULT 0, created_at TEXT NOT NULL,
    FOREIGN KEY (lead_id) REFERENCES aiakilov_leads(id));

CREATE TABLE IF NOT EXISTS aiakilov_students (
    id TEXT PRIMARY KEY, lead_id TEXT, first_name TEXT NOT NULL, last_name TEXT NOT NULL,
    email TEXT, phone TEXT, city TEXT, created_at TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS aiakilov_enrollments (
    id TEXT PRIMARY KEY, student_id TEXT NOT NULL, course_id TEXT NOT NULL,
    enrollment_date TEXT NOT NULL, status TEXT DEFAULT 'active', price REAL,
    payment_status TEXT DEFAULT 'pending', created_at TEXT NOT NULL,
    FOREIGN KEY (student_id) REFERENCES aiakilov_students(id),
    FOREIGN KEY (course_id) REFERENCES aiakilov_courses(id));

CREATE TABLE IF NOT EXISTS aiakilov_payments (
    id TEXT PRIMARY KEY, enrollment_id TEXT NOT NULL, amount REAL NOT NULL,
    method TEXT, paid_at TEXT, created_at TEXT NOT NULL,
    FOREIGN KEY (enrollment_id) REFERENCES aiakilov_enrollments(id));

CREATE TABLE IF NOT EXISTS aiakilov_invoices (
    id TEXT PRIMARY KEY, invoice_number TEXT UNIQUE NOT NULL, enrollment_id TEXT NOT NULL,
    student_id TEXT NOT NULL, course_id TEXT NOT NULL, amount REAL NOT NULL,
    issue_date TEXT NOT NULL, payment_status TEXT DEFAULT 'pending',
    created_at TEXT NOT NULL,
    FOREIGN KEY (enrollment_id) REFERENCES aiakilov_enrollments(id));

CREATE TABLE IF NOT EXISTS aiakilov_ml_predictions (
    id TEXT PRIMARY KEY, lead_id TEXT NOT NULL, model_key TEXT NOT NULL,
    probability REAL NOT NULL, priority TEXT, created_at TEXT NOT NULL,
    FOREIGN KEY (lead_id) REFERENCES aiakilov_leads(id));

CREATE INDEX IF NOT EXISTS idx_aiakilov_leads_status ON aiakilov_leads(status);
CREATE INDEX IF NOT EXISTS idx_aiakilov_leads_source ON aiakilov_leads(lead_source);
CREATE INDEX IF NOT EXISTS idx_aiakilov_leads_course ON aiakilov_leads(course_interest);
CREATE INDEX IF NOT EXISTS idx_aiakilov_enr_student ON aiakilov_enrollments(student_id);
CREATE INDEX IF NOT EXISTS idx_aiakilov_enr_course ON aiakilov_enrollments(course_id);
"""


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def query(sql: str, params: tuple = ()) -> list[dict]:
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def query_one(sql: str, params: tuple = ()) -> dict | None:
    rows = query(sql, params)
    return rows[0] if rows else None


def execute(sql: str, params: tuple = ()) -> None:
    with get_conn() as conn:
        conn.execute(sql, params)
        conn.commit()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def init_db(force: bool = False) -> None:
    """Create the schema and seed once. Idempotent - never drops existing data."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    if force and os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    with get_conn() as conn:
        conn.executescript(SCHEMA)
        conn.commit()
        seeded = conn.execute("SELECT COUNT(*) c FROM aiakilov_leads").fetchone()["c"]
    if seeded == 0:
        _seed()


def _seed() -> None:
    import csv
    import random

    random.seed(42)
    now = _now()
    today = date.today()

    with get_conn() as conn:
        # --- profiles (demo CRM users, one per role) ---
        profiles = [
            ("admin@aiakilov.co.il", "רון אדמין", "ADMIN"),
            ("sales@aiakilov.co.il", "דנה לוי", "SALES"),
            ("courses@aiakilov.co.il", "מאיה בר", "COURSE_MANAGER"),
            ("lecturer@aiakilov.co.il", "ד\"ר עמית רון", "LECTURER"),
            ("marketing@aiakilov.co.il", "אורי שרון", "MARKETING"),
            ("management@aiakilov.co.il", "נועה גל", "MANAGEMENT"),
        ]
        conn.executemany(
            "INSERT OR IGNORE INTO aiakilov_profiles VALUES (?,?,?,?,?)",
            [(str(uuid.uuid4()), e, n, r, now) for e, n, r in profiles],
        )

        # --- courses ---
        course_ids: dict[str, str] = {}
        for i, (name, desc, price, lect, cap, hours, diff) in enumerate(COURSES_SEED):
            cid = str(uuid.uuid4())
            course_ids[name] = cid
            start = today + timedelta(days=14 + i * 21)
            conn.execute(
                "INSERT INTO aiakilov_courses VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (cid, name, desc, price, start.isoformat(),
                 (start + timedelta(days=90)).isoformat(), lect, cap, hours,
                 diff, "active", now),
            )

        # --- leads from the synthetic dataset ---
        with open(CSV_PATH, encoding="utf-8-sig") as fh:
            rows = list(csv.DictReader(fh))

        def num(v, cast=float):
            try:
                return cast(float(v)) if v not in (None, "", "nan") else None
            except (TypeError, ValueError):
                return None

        lead_rows, won = [], []
        for r in rows:
            lid = str(uuid.uuid4())
            created = datetime.now(timezone.utc) - timedelta(days=int(num(r["days_since_created"], int) or 0))
            purchased = int(num(r["purchased"], int) or 0)
            lead_rows.append((
                lid, r["first_name"], r["last_name"], r["email"], r["phone"],
                num(r["age"], int), r["city"], r["occupation"] or None,
                r["education"] or None, r["course_interest"], r["lead_source"],
                r["status"], num(r["budget"]), r["preferred_schedule"],
                num(r["previous_ai_experience"], int) or 0,
                num(r["interaction_count"], int) or 0, r["assigned_sales_rep"], None,
                purchased, created.isoformat(timespec="seconds"), now,
            ))
            if purchased:
                won.append((lid, r, created))

        conn.executemany(
            "INSERT INTO aiakilov_leads VALUES (" + ",".join("?" * 21) + ")", lead_rows
        )

        # --- convert a sample of Won leads into students + enrollments + invoices ---
        sample = random.sample(won, min(400, len(won)))
        students, enrollments, invoices, payments, activities = [], [], [], [], []
        for n, (lid, r, created) in enumerate(sample, start=1):
            sid = str(uuid.uuid4())
            students.append((sid, lid, r["first_name"], r["last_name"], r["email"],
                             r["phone"], r["city"], created.isoformat(timespec="seconds")))
            # ~20% of students buy a second course
            picks = [r["course_interest"]]
            if random.random() < 0.2:
                extra = random.choice([c[0] for c in COURSES_SEED if c[0] != picks[0]])
                picks.append(extra)
            for course_name in picks:
                cid = course_ids[course_name]
                price = dict((c[0], c[2]) for c in COURSES_SEED)[course_name]
                eid = str(uuid.uuid4())
                pay = random.choices(PAYMENT_STATUSES, weights=[0.18, 0.72, 0.05, 0.05])[0]
                edate = (created + timedelta(days=random.randint(1, 21)))
                enrollments.append((eid, sid, cid, edate.date().isoformat(), "active",
                                    price, pay, now))
                inv_no = f"AIA-{edate.year}-{len(invoices) + 1000}"
                invoices.append((str(uuid.uuid4()), inv_no, eid, sid, cid, price,
                                 edate.date().isoformat(), pay, now))
                if pay == "paid":
                    payments.append((str(uuid.uuid4()), eid, price, "כרטיס אשראי (הדגמה)",
                                     edate.date().isoformat(), now))
            if n <= 200:  # activity timeline for a subset keeps seeding fast
                activities.append((str(uuid.uuid4()), lid, "call", "שיחת מכירה ראשונה",
                                   r["assigned_sales_rep"], created.isoformat(timespec="seconds")))

        conn.executemany("INSERT INTO aiakilov_students VALUES (?,?,?,?,?,?,?,?)", students)
        conn.executemany("INSERT INTO aiakilov_enrollments VALUES (?,?,?,?,?,?,?,?)", enrollments)
        conn.executemany("INSERT INTO aiakilov_invoices VALUES (?,?,?,?,?,?,?,?,?)", invoices)
        conn.executemany("INSERT INTO aiakilov_payments VALUES (?,?,?,?,?,?)", payments)
        conn.executemany("INSERT INTO aiakilov_lead_activities VALUES (?,?,?,?,?,?)", activities)

        # a few open follow-up tasks for the demo
        open_leads = conn.execute(
            "SELECT id FROM aiakilov_leads WHERE status IN ('Interested','Follow-up','Counseling') LIMIT 25"
        ).fetchall()
        conn.executemany(
            "INSERT INTO aiakilov_followups VALUES (?,?,?,?,?,?)",
            [(str(uuid.uuid4()), row["id"], "לחזור ללקוח עם הצעת מחיר",
              (today + timedelta(days=random.randint(1, 10))).isoformat(), 0, now)
             for row in open_leads],
        )
        conn.commit()
