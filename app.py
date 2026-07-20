import streamlit as st
import streamlit.components.v1 as components
import json
import os
import sys
import pandas as pd
import random

# Ensure root directory is in sys.path for robust package module resolution on all environments
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.auth import (
    CLASSROOM_PASSWORDS,
    create_activation_token,
    verify_and_clean_activation_token
)
from src.db import (
    init_db,
    load_ratings_from_db,
    save_ratings_to_db,
    save_single_rating_to_db,
    load_all_ratings_from_db,
    load_ratings_rows_by_token,
    check_token_exists,
    delete_ratings_by_token,
    batch_upsert_ratings_to_db
)

# 1. Page Configuration and Theme Styling (Must be the first Streamlit command)
st.set_page_config(
    page_title="LLM Sentence Scorer",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. File Paths
DATABASE_PATH = os.path.join("data", "evaluation_batch_100.json")

# 3. Data Loading Functions
@st.cache_data
def load_database():
    """Load the central database of sentences."""
    if not os.path.exists(DATABASE_PATH):
        st.error(f"Error: Database file `{DATABASE_PATH}` not found in the data directory.")
        return []
    try:
        with open(DATABASE_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data
    except Exception as e:
        st.error(f"Error loading database: {str(e)}")
        return []

def escape_html_display(text):
    if not isinstance(text, str):
        return text
    # Convert characters to HTML entities so markdown parser doesn't touch them
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("$", "&#36;")
        .replace("_", "&#95;")
        .replace("*", "&#42;")
    )

# Load data
database = load_database()
total_sentences = len(database)
# Map original_index to current item for fast lookup
db_by_original_index = {item.get("original_index", i): item for i, item in enumerate(database)} if total_sentences > 0 else {}
candidate_keys = [k for k in database[0].keys() if k not in ["source", "original_index"]] if total_sentences > 0 else []

# --- ACCESS CONTROL INITIALIZATION ---

# Initialize Gate 1 unlocked state with 10-minute refresh persistence check
if "gate1_unlocked" not in st.session_state:
    if verify_and_clean_activation_token():
        st.session_state.gate1_unlocked = True
    else:
        st.session_state.gate1_unlocked = False
else:
    # Continuously clean up expired URL token
    verify_and_clean_activation_token()

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if "token" not in st.session_state:
    st.session_state.token = ""

if "new_token_created" not in st.session_state:
    st.session_state.new_token_created = None

def clear_evaluation_session_states():
    for k in list(st.session_state.keys()):
        if k.startswith("slider_") or k.startswith("container_"):
            del st.session_state[k]
    if "touched_sliders" in st.session_state:
        del st.session_state.touched_sliders

# Gate 1: Classroom Activation Protection (Anti-Bot Barrier)
if not st.session_state.gate1_unlocked:
    st.markdown("<h2 style='text-align: center; margin-top: 100px;'>🔒 Classroom Activation Protection</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center;'>Please enter the Classroom Activation Password to access the evaluation system.</p>", unsafe_allow_html=True)
    
    col_l, col_m, col_r = st.columns([1, 2, 1])
    with col_m:
        activation_input = st.text_input("Enter Classroom Activation Password:", type="password", key="activation_input")
        if st.button("Unlock System", use_container_width=True):
            if activation_input.strip() in CLASSROOM_PASSWORDS:
                st.session_state.gate1_unlocked = True
                # Set 10-minute HMAC signed token in query parameters for refresh persistence
                st.query_params["activation"] = create_activation_token(duration_seconds=600)
                st.success("System unlocked! Proceed to login/registration.")
                st.rerun()
            elif not activation_input.strip():
                st.error("Please enter the password.")
            else:
                st.error("Incorrect password. Access denied.")
    st.stop()

# Gate 2: Token Branching (Reconnection vs. Fresh Start)
if not st.session_state.authenticated:
    st.markdown("<h2 style='text-align: center; margin-top: 100px;'>🔑 Evaluator Authentication</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center;'>Welcome to the LLM Sentence Scorer. Please reconnect using your existing token or start a new session.</p>", unsafe_allow_html=True)
    
    col_l, col_m, col_r = st.columns([1, 2, 1])
    with col_m:
        tab_reconnect, tab_new = st.tabs(["🔌 Seamless Reconnection", "➕ New Evaluator"])
        
        with tab_reconnect:
            st.markdown("### Path A: Reconnect")
            token_input = st.text_input(
                "Enter your 6-character Token:", 
                key="token_reconnect_input",
                placeholder="XXXXXX"
            ).strip().upper()
            
            if st.button("Reconnect Session", use_container_width=True):
                if len(token_input) != 6:
                    st.error("Please enter a valid 6-character token.")
                elif check_token_exists(token_input):
                    st.session_state.authenticated = True
                    st.session_state.token = token_input
                    clear_evaluation_session_states()
                    st.session_state.scores = load_ratings_from_db(token_input)
                    
                    # Restore session navigation pointer
                    if total_sentences > 0:
                        st.session_state.session_indices = list(range(total_sentences))
                        st.session_state.index_ptr = 0
                        for ptr, s_idx in enumerate(st.session_state.session_indices):
                            item = database[s_idx]
                            db_idx = item.get("original_index", s_idx)
                            if str(db_idx) not in st.session_state.scores:
                                st.session_state.index_ptr = ptr
                                break
                    st.success("Welcome back! Reconnected successfully.")
                    st.rerun()
                else:
                    st.error("No historical ratings found for this token. If you are new, please use the 'New Evaluator' tab.")
                    
        with tab_new:
            st.markdown("### Path B: Fresh Start")
            st.write("If you don't have a token, click below to generate one anonymously.")
            if st.button("No, I am a new evaluator. Generate a new Token", use_container_width=True):
                import uuid
                new_tok = uuid.uuid4().hex[:6].upper()
                st.session_state.authenticated = True
                st.session_state.token = new_tok
                st.session_state.new_token_created = new_tok
                clear_evaluation_session_states()
                st.session_state.scores = {}
                st.session_state.index_ptr = 0
                st.success("Token generated successfully!")
                st.rerun()
                
    st.stop()

# Custom clean CSS styles for a polished and minimal look
st.markdown("""
<style>
    /* Adjust Streamlit's default page top/bottom padding to look balanced */
    .block-container {
        padding-top: 2.5rem !important;
        padding-bottom: 1.5rem !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
    }
    
    /* Clean container labels */
    .container-title {
        font-weight: 700;
        font-size: 0.85rem;
        text-transform: uppercase;
        margin-bottom: 4px;
        letter-spacing: 0.5px;
    }
    
    /* Left-bordered container cards with compact spacing */
    .source-container {
        border-left: 5px solid #FF9800;
        background-color: var(--secondary-background-color);
        padding: 8px 12px;
        border-radius: 4px 8px 8px 4px;
        margin-bottom: 6px;
    }
    
    .reference-container {
        border-left: 5px solid #4CAF50;
        background-color: var(--secondary-background-color);
        padding: 8px 12px;
        border-radius: 4px 8px 8px 4px;
        margin-bottom: 6px;
    }
    
    .candidate-container {
        border-left: 5px solid #2196F3;
        background-color: var(--secondary-background-color);
        padding: 8px 12px;
        border-radius: 4px 8px 8px 4px;
        margin-bottom: 6px;
    }
    
    /* Disable selection globally to prevent copying core paper corpus */
    body, .stApp, p, div, span, h1, h2, h3, h4, h5, h6 {
        -webkit-user-select: none !important;
        -moz-user-select: none !important;
        -ms-user-select: none !important;
        user-select: none !important;
    }

    /* Allow selection and copying for code blocks, token displays, and inputs */
    code, .stCodeBlock, pre, .copyable-token, [data-testid="stCodeBlock"], input {
        -webkit-user-select: text !important;
        -moz-user-select: text !important;
        -ms-user-select: text !important;
        user-select: text !important;
    }
</style>
""", unsafe_allow_html=True)

# --- BACKEND CONFIGURATION ---
ADMIN_PASSWORD = "admin"
BLIND_RATING = True  # Hide model names and randomize candidate display order

# 4. State Initialization
if "scores" not in st.session_state:
    if st.session_state.get("authenticated") and "token" in st.session_state:
        st.session_state.scores = load_ratings_from_db(st.session_state.token)
    else:
        st.session_state.scores = {}

if "pending_updates" not in st.session_state:
    st.session_state.pending_updates = {}

if "sync_status" not in st.session_state:
    st.session_state.sync_status = "🟢 Synced to database"

if "last_sync_time" not in st.session_state:
    st.session_state.last_sync_time = time.time()

if "show_warning" not in st.session_state:
    st.session_state.show_warning = False

if "session_indices" not in st.session_state and total_sentences > 0:
    # Use all pre-sampled sentences in order
    st.session_state.session_indices = list(range(total_sentences))
    
    # Set index pointer to first unrated sentence in this list, or 0
    st.session_state.index_ptr = 0
    for ptr, s_idx in enumerate(st.session_state.session_indices):
        item = database[s_idx]
        db_idx = item.get("original_index", s_idx)
        if str(db_idx) not in st.session_state.scores:
            st.session_state.index_ptr = ptr
            break

# Ensure index pointer is valid
if "session_indices" in st.session_state and len(st.session_state.session_indices) > 0:
    st.session_state.index_ptr = max(0, min(st.session_state.index_ptr, len(st.session_state.session_indices) - 1))
else:
    st.session_state.index_ptr = 0

# Keep track of randomized orders for blind scoring to prevent rerendering shuffle on slider click
if "shuffled_candidates" not in st.session_state:
    st.session_state.shuffled_candidates = {}

# 5. Session State Navigation & Sync Functions
def flush_pending_ratings(force=False):
    """
    Flushes pending memory updates to PostgreSQL via an atomic batch UPSERT.
    Status transitions:
      🟡 Pending local changes -> 🔄 Syncing -> 🟢 Synced to database (or 🔴 Sync failed)
    """
    pending = st.session_state.get("pending_updates", {})
    if not pending:
        if st.session_state.get("sync_status") == "🟡 Pending local changes":
            st.session_state.sync_status = "🟢 Synced to database"
        return
        
    token = st.session_state.get("token")
    if not token or not st.session_state.get("authenticated"):
        return

    now = time.time()
    last_sync = st.session_state.get("last_sync_time", 0)
    if not force and (now - last_sync < 0.8):
        return

    st.session_state.sync_status = "🔄 Syncing"
    updates_list = list(pending.values())
    
    try:
        batch_upsert_ratings_to_db(token, updates_list)
        # Safe deletion: only delete items from pending_updates if timestamp matches the snapshot item!
        # If the user edited a rating during sync, the new timestamp in pending_updates will NOT match,
        # preserving the newer edit for the next flush cycle.
        for item in updates_list:
            key = (item["sentence_id"], item["model_name"])
            current = st.session_state.pending_updates.get(key)
            if current and current.get("timestamp") == item.get("timestamp"):
                st.session_state.pending_updates.pop(key, None)
            
        if not st.session_state.pending_updates:
            st.session_state.sync_status = "🟢 Synced to database"
        else:
            st.session_state.sync_status = "🟡 Pending local changes"
            
        st.session_state.last_sync_time = time.time()
    except Exception as e:
        st.session_state.sync_status = "🔴 Sync failed"

def handle_slider_change(db_idx, key):
    if "touched_sliders" not in st.session_state:
        st.session_state.touched_sliders = {}
    st.session_state.touched_sliders[f"{db_idx}_{key}"] = True
    st.session_state.show_toast = True
    
    # Get value from slider key
    slider_key = f"slider_{db_idx}_{key}"
    score = st.session_state.get(slider_key, 0)
    
    # 1. Update local session scores in memory (0ms lag UI response)
    db_idx_str = str(db_idx)
    if db_idx_str not in st.session_state.scores:
        st.session_state.scores[db_idx_str] = {}
    st.session_state.scores[db_idx_str][key] = score
    
    # 2. Queue pending update with timestamp for debounced batch flush
    if "pending_updates" not in st.session_state:
        st.session_state.pending_updates = {}
    st.session_state.pending_updates[(db_idx, key)] = {
        "sentence_id": db_idx,
        "model_name": key,
        "score": score,
        "timestamp": time.time()
    }
    
    # 3. Transition status to pending local changes
    st.session_state.sync_status = "🟡 Pending local changes"

def next_sentence():
    flush_pending_ratings(force=True)
    if "session_indices" not in st.session_state:
        return
    ptr = st.session_state.index_ptr
    s_idx = st.session_state.session_indices[ptr]
    db_idx = database[s_idx].get("original_index", s_idx)
    
    # Check if all candidates for the current sentence are rated/touched
    all_rated = True
    for k in candidate_keys:
        touch_key = f"{db_idx}_{k}"
        is_touched = st.session_state.get("touched_sliders", {}).get(touch_key, False)
        if not is_touched:
            all_rated = False
            break
            
    if all_rated:
        # Navigate to next
        if st.session_state.index_ptr < len(st.session_state.session_indices) - 1:
            st.session_state.index_ptr += 1
            new_s_idx = st.session_state.session_indices[st.session_state.index_ptr]
            new_db_idx = database[new_s_idx].get("original_index", new_s_idx)
            st.session_state.shuffled_candidates.pop(new_db_idx, None)
        st.session_state.show_warning = False
    else:
        st.session_state.show_warning = True

def prev_sentence():
    flush_pending_ratings(force=True)
    if "session_indices" not in st.session_state:
        return
    # Go to prev regardless of validation status
    if st.session_state.index_ptr > 0:
        st.session_state.index_ptr -= 1
        new_s_idx = st.session_state.session_indices[st.session_state.index_ptr]
        new_db_idx = database[new_s_idx].get("original_index", new_s_idx)
        st.session_state.shuffled_candidates.pop(new_db_idx, None)
    st.session_state.show_warning = False

def go_to_ptr(ptr):
    flush_pending_ratings(force=True)
    if "session_indices" not in st.session_state:
        return
    # Go to target ptr regardless of validation status
    if 0 <= ptr < len(st.session_state.session_indices):
        st.session_state.index_ptr = ptr
        new_s_idx = st.session_state.session_indices[ptr]
        new_db_idx = database[new_s_idx].get("original_index", new_s_idx)
        st.session_state.shuffled_candidates.pop(new_db_idx, None)
    st.session_state.show_warning = False

# Main structure
st.markdown("<h3 style='text-align: center; margin-top: -0px; margin-bottom: 15px; font-weight: bold;'>Sentence Scorer</h3>", unsafe_allow_html=True)

if st.session_state.get("new_token_created"):
    st.info("🔑 **Your anonymous evaluation token has been generated:**", icon="⚠️")
    st.code(st.session_state.new_token_created, language=None)
    st.caption("Please copy and save it! You will need it to rejoin this session if your browser crashes or if you change devices.")
    if st.button("I have copied my token. Dismiss this notice.", type="primary", key="dismiss_token_btn"):
        st.session_state.new_token_created = None
        st.rerun()

if total_sentences == 0:
    st.info("Please make sure `central_database.json` contains valid sentence objects and is in the same directory.")
else:
    # Check if admin is active via query parameter or passcode input

    # Check if admin is active via query parameter or passcode input
    is_admin_query = st.query_params.get("admin") == ADMIN_PASSWORD

    # --- SIDEBAR CONTROL PANEL ---
    with st.sidebar:
        st.header("⚙️ Control Panel")

        # Evaluator Token Display & Copy Widget
        if st.session_state.get("authenticated") and st.session_state.get("token"):
            st.subheader("🔑 Evaluator Token")
            st.code(st.session_state.token, language=None)
            st.caption("Copy your token to reconnect on other devices.")
            
            # Status Indicator Badge
            status_text = st.session_state.get("sync_status", "🟢 Synced to database")
            st.markdown(f"**Database Sync Status:**")
            st.info(f"{status_text}")
            st.markdown("---")

        # Check periodic auto-sync flush (>0.8s window)
        flush_pending_ratings(force=False)
        
        # Admin Access Passcode
        st.subheader("🔑 Admin Access")
        admin_passcode = st.text_input("Enter Passcode:", type="password", help="Enter passcode to unlock evaluation dashboard.")
        is_admin = is_admin_query or (admin_passcode == ADMIN_PASSWORD)
        
        st.markdown("---")
        
        # Determine mode and show options based on admin status
        if is_admin:
            app_mode = st.radio("App Mode", ["📝 Rate Sentences", "📊 Analytics Dashboard", "🔍 Browse Database"])
        else:
            app_mode = "📝 Rate Sentences"
            st.info("🔒 Enter the admin passcode to access ")
        
        # Scoring Progress in current session
        session_size = len(st.session_state.session_indices)
        session_rated_count = 0
        for s_idx in st.session_state.session_indices:
            item = database[s_idx]
            db_idx = item.get("original_index", s_idx)
            db_idx_str = str(db_idx)
            if db_idx_str in st.session_state.scores:
                scores_dict = st.session_state.scores[db_idx_str]
                # Count as rated only if all candidate keys have an actual selection (not None)
                if all(scores_dict.get(k) is not None for k in candidate_keys):
                    session_rated_count += 1
        session_completion_pct = (session_rated_count / session_size) * 100 if session_size > 0 else 0
        
        st.subheader("Session Progress")
        st.write(f"Rated: **{session_rated_count}** / {session_size} ({session_completion_pct:.1f}%)")
        st.progress(session_completion_pct / 100.0)
        
        # Jump to sentence dropdown (session scope)
        st.markdown("---")
        st.subheader("🎯 Quick Navigation")
        jump_options = {f"Sentence {i+1}": i for i in range(session_size)}
        selected_jump = st.selectbox(
            "Jump to Sentence:", 
            options=list(jump_options.keys()), 
            index=st.session_state.index_ptr,
            label_visibility="collapsed"
        )
        target_ptr = jump_options[selected_jump]
        if target_ptr != st.session_state.index_ptr:
            go_to_ptr(target_ptr)
            st.rerun()

        # Save and Download Panel - ONLY shown to admin
        if is_admin:
            st.markdown("---")
            st.subheader("💾 Export & Data Management")
            
            # Flush any pending local changes before building export data
            flush_pending_ratings(force=True)
            
            # Pull records exclusively for active evaluator token
            current_tok = st.session_state.get("token", "")
            token_rows = load_ratings_rows_by_token(current_tok) if current_tok else []
            export_dict = {}
            for token, s_idx, model, score in token_rows:
                if token not in export_dict:
                    export_dict[token] = {}
                s_idx_str = str(s_idx)
                if s_idx_str not in export_dict[token]:
                    export_dict[token][s_idx_str] = {}
                export_dict[token][s_idx_str][model] = score
            
            # Download JSON
            json_scores = json.dumps(export_dict, indent=2, ensure_ascii=False)
            st.download_button(
                label="📥 Download My Scores (JSON)",
                data=json_scores,
                file_name=f"llm_scores_{current_tok}.json" if current_tok else "llm_scores.json",
                mime="application/json",
                use_container_width=True
            )
            
            # Download CSV
            if token_rows:
                rows = []
                for token, s_idx, model, score in token_rows:
                    rows.append({
                        "token": token,
                        "sentence_id": s_idx,
                        "model_name": model,
                        "score": score,
                        "source": db_by_original_index.get(s_idx, {}).get("source", ""),
                        "reference": db_by_original_index.get(s_idx, {}).get("reference", "")
                    })
                df_export = pd.DataFrame(rows)
                csv_scores = df_export.to_csv(index=False, encoding='utf-8-sig')
                st.download_button(
                    label="📥 Download My Scores (CSV)",
                    data=csv_scores,
                    file_name=f"llm_scores_{current_tok}.csv" if current_tok else "llm_scores.csv",
                    mime="text/csv",
                    use_container_width=True
                )

            # Reset ratings
            st.markdown("<br><br>", unsafe_allow_html=True)
            if st.button("⚠️ Reset All Scores", type="secondary", use_container_width=True):
                flush_pending_ratings(force=True)
                delete_ratings_by_token(st.session_state.token)
                st.session_state.scores = {}
                st.session_state.touched_sliders = {}
                for k in list(st.session_state.keys()):
                    if k.startswith("slider_"):
                        del st.session_state[k]
                st.toast("Your ratings have been reset!", icon="✅")
                st.rerun()

    # --- MAIN CONTENT AREA ---
    
    # Mode 1: Rating Interface
    if app_mode == "📝 Rate Sentences":
        ptr = st.session_state.index_ptr
        s_idx = st.session_state.session_indices[ptr]
        current_item = database[s_idx]
        db_idx = current_item.get("original_index", s_idx)
        session_size = len(st.session_state.session_indices)
        
        # Show warning at the top of navigation (Next button is nearby)
        if st.session_state.get("show_warning", False):
            st.warning("Warning: There are still candidate sentences on the current page that have not been rated. Please check and complete all ratings before submitting again!")

        # Navigation buttons layout - compact text size
        col_prev, col_num, col_next = st.columns([1, 2, 1])
        with col_prev:
            st.button("⏮️ Previous", on_click=prev_sentence, disabled=(ptr == 0), use_container_width=True)
        with col_num:
            if is_admin:
                st.markdown(f"<div style='text-align: center; font-weight: bold; font-size: 1.1rem; margin-top: 5px;'>Sentence {ptr + 1} / {session_size} (Database ID: #{db_idx})</div>", unsafe_allow_html=True)
            else:
                st.markdown(f"<div style='text-align: center; font-weight: bold; font-size: 1.1rem; margin-top: 5px;'>Sentence {ptr + 1} / {session_size}</div>", unsafe_allow_html=True)
        with col_next:
            st.button("Next ⏭️", on_click=next_sentence, disabled=(ptr == session_size - 1), use_container_width=True)

        # Rating Guidelines Expander
        with st.expander("📖 View Rating Guidelines & Dimensions", expanded=False):
            st.markdown("""
            **Please evaluate the candidate sentences based on the following four dimensions:**
            
            1. 🎯 **Faithfulness**: Does the candidate preserve the original meaning of the source sentence without adding, omitting, or distorting key information?
            2. ✍️ **Grammaticality**: Is the candidate grammatically correct, fluent, natural, and free of syntax errors?
            3. 🔄 **Syntactic Structuring**: Does the candidate restructure the syntax of the source sentence instead of just copying the grammatical frame?
            4. 🔀 **Lexical Diversity**: Does the candidate use diverse vocabulary and synonyms rather than repeating the exact words of the source sentence?
            
            *Score range is **1** (worst) to **10** (best).*
            """)
            
        # Display Source in clean container (Reference is now a blind candidate)
        st.markdown(f"""
        <div class="source-container">
            <div class="container-title" style="color: #FF9800;">Source Sentence</div>
            <div>{escape_html_display(current_item.get('source', ''))}</div>
        </div>
        """, unsafe_allow_html=True)
            
        st.markdown("<hr style='margin:10px 0;' />", unsafe_allow_html=True)

        # Stable shuffle management for Blind Rating
        if BLIND_RATING:
            if db_idx not in st.session_state.shuffled_candidates:
                # Shuffle the keys for this index and save them
                shuffled_keys = candidate_keys.copy()
                random.shuffle(shuffled_keys)
                st.session_state.shuffled_candidates[db_idx] = shuffled_keys
            display_order = st.session_state.shuffled_candidates[db_idx]
        else:
            display_order = candidate_keys

        # Retrieve existing scores for the current sentence
        existing_item_scores = st.session_state.scores.get(str(db_idx), {})
        
        # Initialize touched status for the current sentence
        if "touched_sliders" not in st.session_state:
            st.session_state.touched_sliders = {}
            
        for k in candidate_keys:
            touch_key = f"{db_idx}_{k}"
            if k in existing_item_scores and touch_key not in st.session_state.touched_sliders:
                st.session_state.touched_sliders[touch_key] = True

        # Column headers for Candidate and Score columns
        col_hdr_left, col_hdr_right = st.columns([6.5, 3.5], gap="medium")
        with col_hdr_left:
            st.markdown("<span style='font-size: 0.9rem; font-weight: bold; color: var(--text-color);'>🔍 Candidate Sentences</span>", unsafe_allow_html=True)
        with col_hdr_right:
            st.markdown("<div style='text-align: right; padding-right: 15px; font-size: 0.85rem; font-weight: bold; color: var(--text-color);'>📊 Score (0-10), higher is better</div>", unsafe_allow_html=True)

        # Render candidate rows inside standard bordered containers
        updated_item_scores = {}
        for rank, key in enumerate(display_order):
            candidate_text = current_item.get(key, "*(empty)*")
            display_name = f"Candidate {chr(65 + rank)}" if BLIND_RATING else f"Model: {key}"
            existing_score = existing_item_scores.get(key, 0)
            
            slider_key = f"slider_{db_idx}_{key}"
            if slider_key not in st.session_state:
                st.session_state[slider_key] = existing_score
                
            container_key = f"container_{db_idx}_{key}"
            with st.container(border=True, key=container_key):
                col_text, col_rating = st.columns([6.5, 3.5], gap="medium")
                with col_text:
                    st.markdown(f"<div class='container-title' style='color: #2196F3; margin-bottom: 2px;'>{display_name}</div>", unsafe_allow_html=True)
                    st.markdown(escape_html_display(candidate_text), unsafe_allow_html=True)
                with col_rating:
                    score = st.slider(
                        label=f"Rate {display_name}",
                        min_value=0,
                        max_value=10,
                        value=int(st.session_state[slider_key]),
                        step=1,
                        key=slider_key,
                        label_visibility="collapsed",
                        on_change=handle_slider_change,
                        args=(db_idx, key)
                    )
            updated_item_scores[key] = score

        # Collect and inject custom CSS for touched sliders to turn them green
        touched_css_rules = []
        for k in candidate_keys:
            touch_key = f"{db_idx}_{k}"
            slider_key = f"slider_{db_idx}_{k}"
            container_key = f"container_{db_idx}_{k}"
            is_touched = st.session_state.get("touched_sliders", {}).get(touch_key, False)
            if is_touched and slider_key in st.session_state:
                val = st.session_state[slider_key]
                pct = int(val) * 10
                touched_css_rules.append(f"""
                /* Target the thumb (handle) */
                .st-key-{slider_key} div[data-baseweb="slider"] div[role="slider"],
                .st-key-{container_key} div[data-baseweb="slider"] div[role="slider"] {{
                    background-color: #2e7d32 !important;
                }}
                /* Hover / Focus effects */
                .st-key-{slider_key} div[data-baseweb="slider"] div[role="slider"]:hover,
                .st-key-{container_key} div[data-baseweb="slider"] div[role="slider"]:hover {{
                    box-shadow: 0px 0px 0px 10px rgba(46, 125, 50, 0.16) !important;
                }}
                .st-key-{slider_key} div[data-baseweb="slider"] div[role="slider"]:focus,
                .st-key-{container_key} div[data-baseweb="slider"] div[role="slider"]:focus {{
                    box-shadow: 0px 0px 0px 10px rgba(46, 125, 50, 0.24) !important;
                }}
                /* Target the track background / fill */
                .st-key-{slider_key} div[data-baseweb="slider"] > div > div,
                .st-key-{container_key} div[data-baseweb="slider"] > div > div {{
                    background: linear-gradient(to right, #4caf50 0%, #4caf50 {pct}%, var(--secondary-background-color) {pct}%, var(--secondary-background-color) 100%) !important;
                }}
                /* Target the tick bar if it uses stTickBar */
                .st-key-{slider_key} div[data-testid="stTickBar"],
                .st-key-{container_key} div[data-testid="stTickBar"] {{
                    background: linear-gradient(to right, #4caf50 0%, #4caf50 {pct}%, var(--secondary-background-color) {pct}%, var(--secondary-background-color) 100%) !important;
                }}
                """)
        if touched_css_rules:
            st.markdown(f"<style>{''.join(touched_css_rules)}</style>", unsafe_allow_html=True)

        # Show toast if flag is set
        if st.session_state.get("show_toast", False):
            st.toast("Rating updated!", icon="💾")
            st.session_state.show_toast = False

        # Quick Save indicator
        if is_admin:
            st.caption(f"✓ Current Sentence #{db_idx} rating: { {k: v for k, v in updated_item_scores.items()} }")
        else:
            st.caption("✓ Ratings updated locally. Submit by clicking Next.")

    # Mode 2: Analytics Dashboard
    elif app_mode == "📊 Analytics Dashboard":
        st.subheader("📊 Evaluation Analytics Dashboard")
        
        all_rows = load_all_ratings_from_db()
        if not all_rows:
            st.info("No ratings collected yet. Please rate some sentences first to view analytics!")
        else:
            # Prepare data
            scores_list = []
            for token, s_idx, model, score in all_rows:
                scores_list.append({
                    "Token": token,
                    "Sentence Index": s_idx,
                    "Model": model,
                    "Score": score
                })
            df = pd.DataFrame(scores_list)
            
            # KPI Metrics
            total_rated_sessions = df["Sentence Index"].nunique()
            
            col_kpi1, col_kpi2, col_kpi3 = st.columns(3)
            with col_kpi1:
                st.metric("Total Sentences Rated", f"{total_rated_sessions} / {total_sentences}")
            with col_kpi2:
                overall_avg = df["Score"].mean()
                st.metric("Overall Average Rating", f"{overall_avg:.2f} / 10")
            with col_kpi3:
                model_with_highest_avg = df.groupby("Model")["Score"].mean().idxmax()
                highest_avg_score = df.groupby("Model")["Score"].mean().max()
                st.metric("Top Model", f"{model_with_highest_avg}", f"{highest_avg_score:.2f} avg")

            st.markdown("---")
            
            col_chart1, col_chart2 = st.columns(2)
            
            with col_chart1:
                st.markdown("### 🏆 Average Score by Model")
                avg_scores = df.groupby("Model")["Score"].mean().reset_index().sort_values(by="Score", ascending=False)
                # Plotly or standard bar chart
                st.bar_chart(avg_scores.set_index("Model"), y="Score", color="#FF4B4B")
                
                # Show tabular view of averages
                st.dataframe(
                    avg_scores.rename(columns={"Score": "Average Score"}).style.format({"Average Score": "{:.2f}"}),
                    use_container_width=True
                )
                
            with col_chart2:
                st.markdown("### 📈 Score Distribution by Model")
                # Frequency of scores
                pivot_df = df.pivot_table(index="Score", columns="Model", aggfunc="size", fill_value=0)
                st.line_chart(pivot_df)
                
                # Model statistics table
                st.markdown("#### Model Performance Metrics")
                stats_df = df.groupby("Model")["Score"].agg(["count", "mean", "std", "min", "median", "max"]).reset_index()
                stats_df.columns = ["Model", "Ratings Count", "Mean Score", "Std Dev", "Min", "Median", "Max"]
                st.dataframe(
                    stats_df.style.format({
                        "Mean Score": "{:.2f}",
                        "Std Dev": "{:.2f}"
                    }),
                    use_container_width=True,
                    hide_index=True
                )

            st.markdown("---")
            st.markdown("### 🧐 Model Disagreement (Highest Discrepancy)")
            st.write("These are the sentences where candidate models received the most varied scores (highest standard deviation). These are excellent cases for qualitative analysis.")
            
            # Calculate standard deviation of scores per sentence index
            disagreement = df.groupby("Sentence Index")["Score"].std().reset_index()
            disagreement.columns = ["Sentence Index", "Score StdDev"]
            top_disagreement = disagreement.sort_values(by="Score StdDev", ascending=False).head(5)
            
            for rank, (_, row) in enumerate(top_disagreement.iterrows()):
                s_idx = int(row["Sentence Index"])
                std_val = row["Score StdDev"]
                item = db_by_original_index.get(s_idx, {})
                
                # Calculate average score per model for this sentence index
                sentence_df = df[df["Sentence Index"] == s_idx]
                avg_ratings = sentence_df.groupby("Model")["Score"].mean().to_dict()
                
                st.markdown(f"#### #{rank+1}. Sentence Index {s_idx} (Score StdDev: {std_val:.2f})")
                st.markdown(f"**Source**: {item.get('source', '')}")
                st.markdown(f"**Reference**: {item.get('reference', '')}")
                
                # Present average ratings table
                cols = st.columns(len(avg_ratings))
                for c_idx, (model_name, avg_score) in enumerate(avg_ratings.items()):
                    with cols[c_idx]:
                        st.metric(label=model_name, value=f"{avg_score:.2f}/10")
                st.markdown("<hr style='margin:10px 0; border:0; border-top:1px dashed #ccc;' />", unsafe_allow_html=True)

    # Mode 3: Browse Database
    elif app_mode == "🔍 Browse Database":
        st.subheader("🔍 Browse Database & Ratings")
        st.write("Browse all sentences from the database alongside their ratings.")
        
        browse_data = []
        for i, item in enumerate(database):
            orig_idx = item.get("original_index", i)
            has_rated = "Yes" if str(orig_idx) in st.session_state.scores else "No"
            row = {
                "Index": orig_idx,
                "Rated": has_rated,
                "Source": item.get("source", ""),
                "Reference": item.get("reference", ""),
            }
            # Add scores if rated
            if str(orig_idx) in st.session_state.scores:
                for key in candidate_keys:
                    row[f"Score ({key})"] = st.session_state.scores[str(orig_idx)].get(key, "")
            else:
                for key in candidate_keys:
                    row[f"Score ({key})"] = ""
            browse_data.append(row)
            
        df_browse = pd.DataFrame(browse_data)
        
        # Filter options
        filter_rated = st.selectbox("Filter ratings:", ["All Sentences", "Only Rated", "Only Unrated"])
        if filter_rated == "Only Rated":
            df_filtered = df_browse[df_browse["Rated"] == "Yes"]
        elif filter_rated == "Only Unrated":
            df_filtered = df_browse[df_browse["Rated"] == "No"]
        else:
            df_filtered = df_browse
            
        # Search functionality
        search_query = st.text_input("🔍 Search sentences by text:")
        if search_query:
            df_filtered = df_filtered[
                df_filtered["Source"].str.contains(search_query, case=False, na=False) | 
                df_filtered["Reference"].str.contains(search_query, case=False, na=False)
            ]
            
        st.write(f"Showing {len(df_filtered)} records.")
        st.dataframe(df_filtered, use_container_width=True, hide_index=True)

    # 6. Copy Prevention Script (with exemption for user tokens and code blocks)
    components.html("""
    <script>
        function isCopyable(el) {
            if (!el) return false;
            if (el.nodeType === 3) el = el.parentElement;
            return !!(el && el.closest && el.closest('code, .stCodeBlock, pre, .copyable-token, [data-testid="stCodeBlock"], input'));
        }

        try {
            // Prevent context menu (right-click) on parent window unless copyable element
            window.parent.document.addEventListener('contextmenu', function(e) {
                if (!isCopyable(e.target)) {
                    e.preventDefault();
                }
            });
            // Prevent copy event on parent window unless copyable element or selection
            window.parent.document.addEventListener('copy', function(e) {
                var sel = window.parent.getSelection();
                var anchor = sel ? sel.anchorNode : null;
                if (isCopyable(anchor) || isCopyable(e.target)) {
                    return; // Allow copy
                }
                e.preventDefault();
            });
            // Prevent text selection on parent window body
            window.parent.document.body.style.userSelect = 'none';
            window.parent.document.body.style.webkitUserSelect = 'none';
            window.parent.document.body.style.msUserSelect = 'none';
        } catch (e) {
            console.error("Parent window selection restriction bypassed or inaccessible.");
        }
        
        // Disable within the iframe itself
        document.addEventListener('contextmenu', function(e) {
            if (!isCopyable(e.target)) e.preventDefault();
        });
        document.addEventListener('copy', function(e) {
            var sel = window.getSelection();
            var anchor = sel ? sel.anchorNode : null;
            if (isCopyable(anchor) || isCopyable(e.target)) return;
            e.preventDefault();
        });
        document.body.style.userSelect = 'none';
        document.body.style.webkitUserSelect = 'none';
        document.body.style.msUserSelect = 'none';
    </script>
    """, height=0)
