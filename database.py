import sqlite3
import os
from datetime import datetime, timedelta
import random

DB_PATH = os.path.join(os.path.dirname(__file__), "quiz_data.db")

def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS knowledge_points (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chapter TEXT NOT NULL,
        section TEXT,
        title TEXT NOT NULL,
        level TEXT DEFAULT '重要',
        content TEXT,
        source_file TEXT,
        UNIQUE(chapter, section, title)
    );

    CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        question_text TEXT NOT NULL,
        options TEXT NOT NULL,
        answer TEXT NOT NULL,
        explanation TEXT,
        chapter TEXT NOT NULL,
        section TEXT,
        source_file TEXT,
        question_type TEXT DEFAULT 'single',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS wrong_questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        question_id INTEGER NOT NULL,
        times_wrong INTEGER DEFAULT 1,
        last_reviewed TEXT,
        FOREIGN KEY (question_id) REFERENCES questions(id)
    );

    CREATE TABLE IF NOT EXISTS study_plan (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        days INTEGER NOT NULL,
        daily_count INTEGER NOT NULL,
        start_date TEXT,
        status TEXT DEFAULT 'active',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS daily_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plan_id INTEGER,
        date TEXT NOT NULL,
        questions_done INTEGER DEFAULT 0,
        correct_count INTEGER DEFAULT 0,
        FOREIGN KEY (plan_id) REFERENCES study_plan(id)
    );

    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    );
    """)
    conn.commit()
    conn.close()

def insert_knowledge_point(chapter, section, title, level, content, source_file):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT OR IGNORE INTO knowledge_points (chapter, section, title, level, content, source_file)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (chapter, section, title, level, content, source_file))
    conn.commit()
    rid = cur.lastrowid
    conn.close()
    return rid

def insert_question(question_text, options, answer, explanation, chapter, section, source_file):
    import json
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO questions (question_text, options, answer, explanation, chapter, section, source_file)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (question_text, json.dumps(options, ensure_ascii=False), answer, explanation, chapter, section, source_file))
    conn.commit()
    rid = cur.lastrowid
    conn.close()
    return rid

def get_all_questions():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM questions ORDER BY chapter, id")
    rows = cur.fetchall()
    conn.close()
    return rows

def get_questions_by_chapter(chapter):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM questions WHERE chapter=? ORDER BY id", (chapter,))
    rows = cur.fetchall()
    conn.close()
    return rows

def get_questions_by_knowledge(knowledge_title):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT q.* FROM questions q
        JOIN knowledge_points kp ON q.chapter = kp.chapter AND (q.section = kp.section OR q.chapter = kp.title)
        WHERE kp.title = ?
    """, (knowledge_title,))
    rows = cur.fetchall()
    conn.close()
    return rows

def add_wrong_question(question_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT OR IGNORE INTO wrong_questions (question_id, times_wrong, last_reviewed)
        VALUES (?, 1, datetime('now'))
    """, (question_id,))
    if cur.rowcount == 0:
        cur.execute("""
            UPDATE wrong_questions SET times_wrong = times_wrong + 1,
            last_reviewed = datetime('now') WHERE question_id=?
        """, (question_id,))
    conn.commit()
    conn.close()

def get_wrong_questions():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT q.*, w.times_wrong, w.last_reviewed
        FROM questions q
        JOIN wrong_questions w ON q.id = w.question_id
        ORDER BY w.last_reviewed DESC
    """)
    rows = cur.fetchall()
    conn.close()
    return rows

def remove_wrong_question(question_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM wrong_questions WHERE question_id=?", (question_id,))
    conn.commit()
    conn.close()

def get_chapters():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT chapter FROM questions ORDER BY chapter")
    rows = cur.fetchall()
    conn.close()
    return [r['chapter'] for r in rows]

def get_knowledge_points():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM knowledge_points ORDER BY chapter, section, title")
    rows = cur.fetchall()
    conn.close()
    return rows

def get_knowledge_points_by_chapter(chapter):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM knowledge_points WHERE chapter=? ORDER BY section, title", (chapter,))
    rows = cur.fetchall()
    conn.close()
    return rows

def set_study_plan(days, daily_count):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE study_plan SET status='inactive' WHERE status='active'")
    cur.execute("""
        INSERT INTO study_plan (days, daily_count, start_date, status)
        VALUES (?, ?, date('now'), 'active')
    """, (days, daily_count))
    conn.commit()
    conn.close()

def get_active_plan():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM study_plan WHERE status='active' ORDER BY id DESC LIMIT 1")
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def record_daily(plan_id, questions_done, correct_count):
    today = datetime.now().strftime('%Y-%m-%d')
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO daily_records (plan_id, date, questions_done, correct_count)
        VALUES (?, ?, ?, ?)
    """, (plan_id, today, questions_done, correct_count))
    conn.commit()
    conn.close()

def get_records(plan_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM daily_records WHERE plan_id=? ORDER BY date", (plan_id,))
    rows = cur.fetchall()
    conn.close()
    return rows

def get_stats():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) as total FROM questions")
    total = cur.fetchone()['total']
    cur.execute("SELECT COUNT(*) as wrong FROM wrong_questions")
    wrong = cur.fetchone()['wrong']
    conn.close()
    return total, wrong

def delete_all_questions():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM questions")
    cur.execute("DELETE FROM wrong_questions")
    conn.commit()
    conn.close()

def delete_all_knowledge_points():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM knowledge_points")
    conn.commit()
    conn.close()