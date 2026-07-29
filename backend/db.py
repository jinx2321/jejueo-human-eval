import streamlit as st
from sqlalchemy import text

# --- DATABASE PERSISTENCE SETUP ---
conn = st.connection("sql", type="sql", pool_pre_ping=True, pool_recycle=300)

RATINGS_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS ratings (
        token VARCHAR(64) NOT NULL,
        direction VARCHAR(32) NOT NULL,
        sentence_id INTEGER NOT NULL,
        model_name VARCHAR(255) NOT NULL,
        score INTEGER NOT NULL,
        timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
        PRIMARY KEY (token, direction, sentence_id, model_name)
    );
"""

# One free-text note per (evaluator, direction, sentence) - covers the whole
# sentence, not any single candidate.
NOTES_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS notes (
        token VARCHAR(64) NOT NULL,
        direction VARCHAR(32) NOT NULL,
        sentence_id INTEGER NOT NULL,
        note TEXT NOT NULL,
        timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
        PRIMARY KEY (token, direction, sentence_id)
    );
"""

# Persists which group (0..NUM_GROUPS-1) each evaluator token was assigned to.
# Assignment happens once, at first login (see get_or_assign_group), and is
# looked up (not recomputed) on every later reconnect so a token always gets
# back the same sentence slice.
GROUP_ASSIGNMENTS_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS group_assignments (
        token VARCHAR(64) PRIMARY KEY,
        group_index INTEGER NOT NULL,
        assigned_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
    );
"""

def init_db():
    try:
        with conn.session as s:
            s.execute(text(RATINGS_TABLE_SQL))
            s.execute(text(NOTES_TABLE_SQL))
            s.execute(text(GROUP_ASSIGNMENTS_TABLE_SQL))
            s.commit()
    except Exception:
        # Retry connection if serverless SSL connection was closed by idle timeout
        with conn.session as s:
            s.execute(text(RATINGS_TABLE_SQL))
            s.execute(text(NOTES_TABLE_SQL))
            s.execute(text(GROUP_ASSIGNMENTS_TABLE_SQL))
            s.commit()

def get_or_assign_group(token, num_groups):
    """
    Return this token's evaluation group. First login for a token claims
    whichever group currently has the fewest assigned tokens (ties go to the
    lowest index), so as long as at most num_groups distinct tokens have ever
    logged in, every one of them gets a distinct group - no two evaluators
    are ever handed the same sentence slice until groups must start doubling
    up beyond that. Later logins just look up the stored assignment.
    """
    init_db()
    with conn.session as s:
        existing = s.execute(
            text("SELECT group_index FROM group_assignments WHERE token = :token"),
            params={"token": token}
        ).scalar()
        if existing is not None:
            return existing

        counts = dict(s.execute(
            text("SELECT group_index, COUNT(*) FROM group_assignments GROUP BY group_index")
        ).fetchall())
        least_loaded = min(range(num_groups), key=lambda g: counts.get(g, 0))

        s.execute(
            text("""
                INSERT INTO group_assignments (token, group_index)
                VALUES (:token, :group_index)
                ON CONFLICT (token) DO NOTHING;
            """),
            params={"token": token, "group_index": least_loaded}
        )
        s.commit()

        assigned = s.execute(
            text("SELECT group_index FROM group_assignments WHERE token = :token"),
            params={"token": token}
        ).scalar()
    return assigned

def load_all_group_assignments():
    init_db()
    with conn.session as s:
        result = s.execute(text("SELECT token, group_index FROM group_assignments ORDER BY assigned_at"))
        rows = result.fetchall()
    return rows

def load_ratings_from_db(token, direction):
    init_db()
    with conn.session as s:
        result = s.execute(
            text("SELECT sentence_id, model_name, score FROM ratings WHERE token = :token AND direction = :direction"),
            params={"token": token, "direction": direction}
        )
        rows = result.fetchall()

    scores = {}
    for sentence_id, model_name, score in rows:
        s_id_str = str(sentence_id)
        if s_id_str not in scores:
            scores[s_id_str] = {}
        scores[s_id_str][model_name] = score
    return scores

def save_ratings_to_db(token, direction, sentence_id, model_scores):
    init_db()
    with conn.session as s:
        for model_name, score in model_scores.items():
            s.execute(
                text("""
                    INSERT INTO ratings (token, direction, sentence_id, model_name, score, timestamp)
                    VALUES (:token, :direction, :sentence_id, :model_name, :score, CURRENT_TIMESTAMP)
                    ON CONFLICT (token, direction, sentence_id, model_name)
                    DO UPDATE SET score = EXCLUDED.score, timestamp = EXCLUDED.timestamp;
                """),
                params={
                    "token": token,
                    "direction": direction,
                    "sentence_id": int(sentence_id),
                    "model_name": model_name,
                    "score": int(score)
                }
            )
        s.commit()

def save_single_rating_to_db(token, direction, sentence_id, model_name, score):
    init_db()
    with conn.session as s:
        s.execute(
            text("""
                INSERT INTO ratings (token, direction, sentence_id, model_name, score, timestamp)
                VALUES (:token, :direction, :sentence_id, :model_name, :score, CURRENT_TIMESTAMP)
                ON CONFLICT (token, direction, sentence_id, model_name)
                DO UPDATE SET score = EXCLUDED.score, timestamp = EXCLUDED.timestamp;
            """),
            params={
                "token": token,
                "direction": direction,
                "sentence_id": int(sentence_id),
                "model_name": model_name,
                "score": int(score)
            }
        )
        s.commit()

def load_all_ratings_from_db():
    init_db()
    with conn.session as s:
        result = s.execute(text("SELECT token, direction, sentence_id, model_name, score FROM ratings"))
        rows = result.fetchall()
    return rows

def load_ratings_rows_by_token(token):
    init_db()
    with conn.session as s:
        result = s.execute(
            text("SELECT token, direction, sentence_id, model_name, score FROM ratings WHERE token = :token"),
            params={"token": token}
        )
        rows = result.fetchall()
    return rows

def check_token_exists(token):
    init_db()
    with conn.session as s:
        result = s.execute(
            text("SELECT COUNT(*) FROM ratings WHERE token = :token"),
            params={"token": token}
        )
        count = result.scalar()
    return count > 0

def delete_ratings_by_token(token):
    init_db()
    with conn.session as s:
        s.execute(
            text("DELETE FROM ratings WHERE token = :token"),
            params={"token": token}
        )
        s.execute(
            text("DELETE FROM notes WHERE token = :token"),
            params={"token": token}
        )
        s.commit()

def load_notes_from_db(token, direction):
    init_db()
    with conn.session as s:
        result = s.execute(
            text("SELECT sentence_id, note FROM notes WHERE token = :token AND direction = :direction"),
            params={"token": token, "direction": direction}
        )
        rows = result.fetchall()
    return {str(sentence_id): note for sentence_id, note in rows}

def save_note_to_db(token, direction, sentence_id, note):
    init_db()
    with conn.session as s:
        if note:
            s.execute(
                text("""
                    INSERT INTO notes (token, direction, sentence_id, note, timestamp)
                    VALUES (:token, :direction, :sentence_id, :note, CURRENT_TIMESTAMP)
                    ON CONFLICT (token, direction, sentence_id)
                    DO UPDATE SET note = EXCLUDED.note, timestamp = EXCLUDED.timestamp;
                """),
                params={
                    "token": token,
                    "direction": direction,
                    "sentence_id": int(sentence_id),
                    "note": note
                }
            )
        else:
            # Empty note: just remove the row instead of storing blank text
            s.execute(
                text("DELETE FROM notes WHERE token = :token AND direction = :direction AND sentence_id = :sentence_id"),
                params={"token": token, "direction": direction, "sentence_id": int(sentence_id)}
            )
        s.commit()

def load_all_notes_from_db():
    init_db()
    with conn.session as s:
        result = s.execute(text("SELECT token, direction, sentence_id, note FROM notes"))
        rows = result.fetchall()
    return rows

from datetime import datetime, timezone

def batch_upsert_ratings_to_db(token, updates_list):
    """
    Executes an atomic batch UPSERT for multiple rating updates under a single database session.
    Uses timestamp-aware conflict resolution (WHERE EXCLUDED.timestamp >= ratings.timestamp)
    to guarantee older out-of-order writes never overwrite newer rating values.
    Each item in updates_list must include a "direction" key.
    """
    if not updates_list or not token:
        return
    init_db()
    with conn.session as s:
        for item in updates_list:
            raw_ts = item.get("timestamp")
            if isinstance(raw_ts, (int, float)):
                ts_val = datetime.fromtimestamp(raw_ts, tz=timezone.utc)
            elif isinstance(raw_ts, datetime):
                ts_val = raw_ts
            else:
                ts_val = datetime.now(timezone.utc)

            s.execute(
                text("""
                    INSERT INTO ratings (token, direction, sentence_id, model_name, score, timestamp)
                    VALUES (:token, :direction, :sentence_id, :model_name, :score, :timestamp_val)
                    ON CONFLICT (token, direction, sentence_id, model_name)
                    DO UPDATE SET score = EXCLUDED.score, timestamp = EXCLUDED.timestamp
                    WHERE EXCLUDED.timestamp >= ratings.timestamp;
                """),
                params={
                    "token": token,
                    "direction": str(item["direction"]),
                    "sentence_id": int(item["sentence_id"]),
                    "model_name": str(item["model_name"]),
                    "score": int(item["score"]),
                    "timestamp_val": ts_val
                }
            )
        s.commit()
