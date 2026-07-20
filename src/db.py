import streamlit as st
from sqlalchemy import text

# --- DATABASE PERSISTENCE SETUP ---
conn = st.connection("sql", type="sql", pool_pre_ping=True, pool_recycle=300)

def init_db():
    try:
        with conn.session as s:
            s.execute(text("""
                CREATE TABLE IF NOT EXISTS ratings (
                    token VARCHAR(64) NOT NULL,
                    sentence_id INTEGER NOT NULL,
                    model_name VARCHAR(255) NOT NULL,
                    score INTEGER NOT NULL,
                    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
                    PRIMARY KEY (token, sentence_id, model_name)
                );
            """))
            s.commit()
    except Exception:
        # Retry connection if serverless SSL connection was closed by idle timeout
        with conn.session as s:
            s.execute(text("""
                CREATE TABLE IF NOT EXISTS ratings (
                    token VARCHAR(64) NOT NULL,
                    sentence_id INTEGER NOT NULL,
                    model_name VARCHAR(255) NOT NULL,
                    score INTEGER NOT NULL,
                    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
                    PRIMARY KEY (token, sentence_id, model_name)
                );
            """))
            s.commit()

def load_ratings_from_db(token):
    init_db()
    with conn.session as s:
        result = s.execute(
            text("SELECT sentence_id, model_name, score FROM ratings WHERE token = :token"),
            params={"token": token}
        )
        rows = result.fetchall()
    
    scores = {}
    for sentence_id, model_name, score in rows:
        s_id_str = str(sentence_id)
        if s_id_str not in scores:
            scores[s_id_str] = {}
        scores[s_id_str][model_name] = score
    return scores

def save_ratings_to_db(token, sentence_id, model_scores):
    init_db()
    with conn.session as s:
        for model_name, score in model_scores.items():
            s.execute(
                text("""
                    INSERT INTO ratings (token, sentence_id, model_name, score, timestamp)
                    VALUES (:token, :sentence_id, :model_name, :score, CURRENT_TIMESTAMP)
                    ON CONFLICT (token, sentence_id, model_name)
                    DO UPDATE SET score = EXCLUDED.score, timestamp = EXCLUDED.timestamp;
                """),
                params={
                    "token": token,
                    "sentence_id": int(sentence_id),
                    "model_name": model_name,
                    "score": int(score)
                }
            )
        s.commit()

def save_single_rating_to_db(token, sentence_id, model_name, score):
    init_db()
    with conn.session as s:
        s.execute(
            text("""
                INSERT INTO ratings (token, sentence_id, model_name, score, timestamp)
                VALUES (:token, :sentence_id, :model_name, :score, CURRENT_TIMESTAMP)
                ON CONFLICT (token, sentence_id, model_name)
                DO UPDATE SET score = EXCLUDED.score, timestamp = EXCLUDED.timestamp;
            """),
            params={
                "token": token,
                "sentence_id": int(sentence_id),
                "model_name": model_name,
                "score": int(score)
            }
        )
        s.commit()

def load_all_ratings_from_db():
    init_db()
    with conn.session as s:
        result = s.execute(text("SELECT token, sentence_id, model_name, score FROM ratings"))
        rows = result.fetchall()
    return rows

def load_ratings_rows_by_token(token):
    init_db()
    with conn.session as s:
        result = s.execute(
            text("SELECT token, sentence_id, model_name, score FROM ratings WHERE token = :token"),
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
        s.commit()
