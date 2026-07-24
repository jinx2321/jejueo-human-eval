import streamlit as st
import streamlit.components.v1 as components
import json
import os
import sys
import time
import pandas as pd
import random

# Ensure root directory is in sys.path for robust package module resolution on all environments
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from backend.auth import (
    NUM_GROUPS,
    group_index_for_token,
    create_activation_token,
    verify_and_clean_activation_token
)
from backend.db import (
    init_db,
    load_ratings_from_db,
    save_ratings_to_db,
    save_single_rating_to_db,
    load_all_ratings_from_db,
    load_ratings_rows_by_token,
    delete_ratings_by_token,
    batch_upsert_ratings_to_db,
    load_notes_from_db,
    save_note_to_db,
    load_all_notes_from_db
)

# 1. Page Configuration and Theme Styling (Must be the first Streamlit command)
st.set_page_config(
    page_title="제주어-표준어 번역 평가",
    page_icon="🍊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. Evaluation Direction & File Paths
DIRECTIONS = {
    "jj2ko": {
        "label": "제주어 → 표준어",
        "path": os.path.join("data", "jejueo_to_standard.json"),
        "source_label": "제주어 원문",
        "candidate_label": "표준어 후보",
    },
    "ko2jj": {
        "label": "표준어 → 제주어",
        "path": os.path.join("data", "standard_to_jejueo.json"),
        "source_label": "표준어 원문",
        "candidate_label": "제주어 후보",
    },
}
KOREAN_ORDINALS = ["가", "나", "다", "라", "마", "바", "사", "아", "자", "차"]

# Each direction's sentences are split into NUM_GROUPS contiguous, non-overlapping
# blocks so every evaluator (assigned a group index via a hash of their token,
# see backend.auth.group_index_for_token) reviews a distinct slice, and the
# groups together cover the full dataset with no overlap.
#
# jj2ko and ko2jj are parallel corpora: sentence i in one direction's file is the
# same underlying sentence pair as sentence i in the other. Rotating the block
# assignment by one group per direction guarantees no evaluator is ever assigned
# the same underlying sentence in both directions, while each direction is still
# split into non-overlapping blocks that fully cover it.
DIRECTION_ROTATION = {"jj2ko": 0, "ko2jj": 1}

def get_assigned_indices(total, group_index, direction):
    """Return this evaluator's assigned sentence indices for one direction.

    group_index=None means unrestricted/full access. Otherwise the total range
    is split into NUM_GROUPS near-equal contiguous blocks, rotated per
    direction (see DIRECTION_ROTATION) so a given evaluator's blocks never
    line up across the two directions.
    """
    if group_index is None:
        return list(range(total))
    n = NUM_GROUPS
    idx = (group_index + DIRECTION_ROTATION.get(direction, 0)) % n
    base, remainder = divmod(total, n)
    start = idx * base + min(idx, remainder)
    end = start + base + (1 if idx < remainder else 0)
    return list(range(start, end))

# 3. Data Loading Functions
@st.cache_data
def load_database(path):
    """Load a sentence database file for one evaluation direction."""
    if not os.path.exists(path):
        st.error(f"오류: 데이터베이스 파일 `{path}`을(를) 찾을 수 없습니다.")
        return []
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data
    except Exception as e:
        st.error(f"데이터베이스 로딩 오류: {str(e)}")
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

# Load data for both directions (cached individually per file path)
all_databases = {d: load_database(cfg["path"]) for d, cfg in DIRECTIONS.items()}
db_by_original_index = {
    d: ({item.get("original_index", i): item for i, item in enumerate(db)} if len(db) > 0 else {})
    for d, db in all_databases.items()
}
RESERVED_SENTENCE_KEYS = {"source", "original_index", "example_id"}
candidate_keys_by_direction = {
    d: ([k for k in db[0].keys() if k not in RESERVED_SENTENCE_KEYS] if len(db) > 0 else [])
    for d, db in all_databases.items()
}

# --- ACCESS CONTROL INITIALIZATION ---

def clear_evaluation_session_states():
    for k in list(st.session_state.keys()):
        if k.startswith("slider_") or k.startswith("container_"):
            del st.session_state[k]
    if "touched_sliders" in st.session_state:
        del st.session_state.touched_sliders
    st.session_state.dir_state = {}

def log_in_as(token):
    st.session_state.gate1_unlocked = True
    st.session_state.authenticated = True
    # No real names anywhere: whatever token the evaluator types is both their
    # login identity and the only thing persisted with scores/notes/exports.
    # Their group (which slice of each direction they see) is derived from a
    # stable hash of that token, not a fixed roster.
    st.session_state.token = token
    st.session_state.evaluator_group = group_index_for_token(token)

# Initialize login state with 10-minute refresh persistence check
if "gate1_unlocked" not in st.session_state:
    verified_token = verify_and_clean_activation_token()
    if verified_token is not None:
        log_in_as(verified_token)
    else:
        st.session_state.gate1_unlocked = False
        st.session_state.authenticated = False
        st.session_state.token = ""
else:
    # Continuously clean up expired URL token
    verify_and_clean_activation_token()

# Gate: Consent + free-text token entry (doubles as anti-bot barrier)
if not st.session_state.gate1_unlocked:
    st.markdown("<h2 style='text-align: center; margin-top: 100px;'>🍊 제주어-표준어 번역 평가 참여</h2>", unsafe_allow_html=True)

    col_l, col_m, col_r = st.columns([1, 2, 1])
    with col_m:
        st.markdown("""
        ##### 연구 참여 안내
        - 이 설문은 제주어–표준어 번역 품질을 사람이 직접 평가하는 연구입니다.
        - 본 평가는 만 18세 이상이며, 제주도민으로서 제주어를 능숙하게 구사할 수 있는 분을 대상으로 합니다.
        - 각 문항의 답변은 선택하거나 입력하는 즉시 연구 데이터베이스에 저장됩니다.
        - 평가 결과와 선택적으로 작성하신 의견은 연구 및 논문 작성에 사용될 수 있습니다.
        - 실명은 수집하지 않으며, 응답은 직접 정한 참여자 아이디로 저장됩니다. 아이디에 이름이나 연락처 등 개인정보를 입력하지 마세요.
        - 참여는 자유이며 언제든지 평가를 중단할 수 있습니다. 다만 중단 전에 입력한 답변은 자동으로 삭제되지 않습니다.
        - 문의사항은 담당 연구자에게 연락해주세요.
        """)

        with st.expander("▶ 자세한 연구 안내 보기"):
            st.markdown("""
            **1. 연구 목적**

            본 연구는 제주어–표준어 번역 시스템이 생성한 번역문의 품질을 제주어 화자가 직접 평가하는 것을 목적으로 합니다. 평가 결과는 번역 시스템의 품질을 분석하고 관련 연구 및 논문을 작성하는 데 사용됩니다.

            **2. 참여 대상 및 평가 내용**

            본 연구는 만 18세 이상이며, 제주도민으로서 제주어를 능숙하게 이해하고 구사할 수 있는 분을 대상으로 합니다.

            참여자는 제주어 또는 표준어 원문과 번역문을 읽고 번역 품질을 평가합니다. 필요한 경우 번역에서 발견한 특이사항이나 의견을 선택적으로 작성할 수 있습니다.

            **3. 답변 저장 및 참여 중단**

            각 문항의 답변은 전체 평가를 최종 제출할 때가 아니라, 답변을 선택하거나 입력하는 즉시 연구 데이터베이스에 저장됩니다.

            연구 참여는 전적으로 자유이며, 평가 도중 언제든지 브라우저를 닫거나 평가를 중단할 수 있습니다. 참여하지 않거나 중단하더라도 어떠한 불이익도 없습니다.

            다만 평가를 중단하더라도 중단 전에 입력한 답변은 자동으로 삭제되지 않습니다. 저장된 답변의 삭제를 원하는 경우 참여자 아이디와 함께 담당 연구자에게 연락해주세요.

            **4. 수집되는 정보**

            본 연구에서는 다음 정보를 수집합니다.

            - 참여자 아이디
            - 각 문항의 평가 결과
            - 선택적으로 작성한 의견
            - 답변이 저장된 시각

            실명은 수집하지 않습니다. 참여자 아이디에는 이름, 생년월일, 전화번호, 이메일 등 본인을 식별할 수 있는 정보를 입력하지 마세요.

            **5. 데이터 이용 및 보관**

            수집된 데이터는 제주어–표준어 번역 품질 분석과 관련 연구 및 논문 작성에 사용됩니다.

            논문에서는 평가 결과를 주로 여러 참여자의 결과를 합산한 형태로 보고합니다. 선택적으로 작성한 의견은 개인을 식별할 수 있는 내용을 제거한 후 연구 자료나 논문에서 예시로 사용될 수 있습니다.

            **6. 예상되는 위험 및 이익**

            본 연구에서는 일상적인 언어 판단 이상의 특별한 위험을 예상하지 않습니다. 다만 반복적인 문장 평가로 피로감을 느낄 수 있으며, 원할 경우 언제든지 평가를 중단할 수 있습니다.

            연구 참여로 인한 직접적인 이익은 없을 수 있으나, 평가 결과는 제주어 번역 기술의 품질을 분석하고 개선하기 위한 연구에 활용됩니다.

            **7. 문의 및 데이터 삭제 요청**

            연구 내용 또는 저장된 데이터의 삭제에 관한 문의는 아래 담당 연구자에게 연락해주세요.

            - 담당 연구자: 황지우
            - 소속: Technical University of Munich
            - 이메일: jiwoo.hwang@tum.de
            """)

        st.markdown("##### 참여 확인")
        eligibility_confirmed = st.checkbox("본인은 만 18세 이상이며, 제주도민으로서 제주어를 능숙하게 구사할 수 있습니다.", key="eligibility_checkbox")
        consent_given = st.checkbox("본인은 답변이 입력 즉시 저장된다는 점을 포함하여 위 안내를 읽고 이해하였으며, 자발적으로 연구 참여에 동의합니다.", key="consent_checkbox")

        st.markdown("---")
        st.markdown("<p style='text-align: center;'>사용하실 아이디를 자유롭게 입력해주세요. (다른 분과 겹치지 않게 정해주세요)</p>", unsafe_allow_html=True)
        token_input = st.text_input(
            "아이디를 입력해주세요.",
            key="token_input",
            placeholder="예: myeval01",
            label_visibility="collapsed",
        )
        if st.button("참여하기", use_container_width=True):
            entered_token = token_input.strip()
            if not eligibility_confirmed:
                st.error("참여하려면 먼저 만 18세 이상이며, 제주어를 능숙하게 구사할 수 있는 제주도민임을 확인해주세요.")
            elif not consent_given:
                st.error("참여하려면 먼저 답변 저장 방식을 포함한 연구 참여 안내를 확인하고 참여에 동의해주세요.")
            elif not entered_token:
                st.error("아이디를 입력해주세요.")
            else:
                log_in_as(entered_token)
                clear_evaluation_session_states()
                # Set 10-minute HMAC signed token in query parameters for refresh persistence
                st.query_params["activation"] = create_activation_token(entered_token, duration_seconds=600)
                st.success("확인되었습니다! 계속 진행해주세요.")
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

    .candidate-container {
        border-left: 5px solid #2196F3;
        background-color: var(--secondary-background-color);
        padding: 8px 12px;
        border-radius: 4px 8px 8px 4px;
        margin-bottom: 6px;
    }

    /* Disable selection globally to prevent copying core corpus */
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
SCORE_MIN = 0
SCORE_MAX = 100

# 4. State Initialization
if "direction" not in st.session_state:
    st.session_state.direction = list(DIRECTIONS.keys())[0]

if "dir_state" not in st.session_state:
    st.session_state.dir_state = {}

if "pending_updates" not in st.session_state:
    st.session_state.pending_updates = {}

if "sync_status" not in st.session_state:
    st.session_state.sync_status = "🟢 데이터베이스와 동기화됨"

if "last_sync_time" not in st.session_state:
    st.session_state.last_sync_time = time.time()

if "show_warning" not in st.session_state:
    st.session_state.show_warning = False

if "touched_sliders" not in st.session_state:
    st.session_state.touched_sliders = {}

def get_dir_state(direction):
    """Lazily initialize (and cache) per-direction scores + navigation state."""
    if direction not in st.session_state.dir_state:
        db = all_databases.get(direction, [])
        total = len(db)
        scores = {}
        notes = {}
        if st.session_state.get("authenticated") and st.session_state.get("token"):
            scores = load_ratings_from_db(st.session_state.token, direction)
            notes = load_notes_from_db(st.session_state.token, direction)
        session_indices = get_assigned_indices(total, st.session_state.get("evaluator_group"), direction)
        index_ptr = 0
        for ptr, s_idx in enumerate(session_indices):
            item = db[s_idx]
            db_idx = item.get("original_index", s_idx)
            if str(db_idx) not in scores:
                index_ptr = ptr
                break
        st.session_state.dir_state[direction] = {
            "scores": scores,
            "notes": notes,
            "session_indices": session_indices,
            "index_ptr": index_ptr,
            "shuffled_candidates": {},
        }
    ds = st.session_state.dir_state[direction]
    # Ensure index pointer is valid
    if len(ds["session_indices"]) > 0:
        ds["index_ptr"] = max(0, min(ds["index_ptr"], len(ds["session_indices"]) - 1))
    else:
        ds["index_ptr"] = 0
    return ds

# 5. Session State Navigation & Sync Functions
def flush_pending_ratings(force=False):
    """
    Flushes pending memory updates to PostgreSQL via an atomic batch UPSERT.
    Status transitions:
      🟡 로컬 변경사항 대기 중 -> 🔄 동기화 중 -> 🟢 데이터베이스와 동기화됨 (또는 🔴 동기화 실패)
    """
    pending = st.session_state.get("pending_updates", {})
    if not pending:
        if st.session_state.get("sync_status") == "🟡 로컬 변경사항 대기 중":
            st.session_state.sync_status = "🟢 데이터베이스와 동기화됨"
        return

    token = st.session_state.get("token")
    if not token or not st.session_state.get("authenticated"):
        return

    now = time.time()
    last_sync = st.session_state.get("last_sync_time", 0)
    if not force and (now - last_sync < 0.8):
        return

    st.session_state.sync_status = "🔄 동기화 중"
    updates_list = list(pending.values())

    try:
        batch_upsert_ratings_to_db(token, updates_list)
        # Safe deletion: only delete items from pending_updates if timestamp matches the snapshot item!
        # If the user edited a rating during sync, the new timestamp in pending_updates will NOT match,
        # preserving the newer edit for the next flush cycle.
        for item in updates_list:
            key = (item["direction"], item["sentence_id"], item["model_name"])
            current = st.session_state.pending_updates.get(key)
            if current and current.get("timestamp") == item.get("timestamp"):
                st.session_state.pending_updates.pop(key, None)

        if not st.session_state.pending_updates:
            st.session_state.sync_status = "🟢 데이터베이스와 동기화됨"
        else:
            st.session_state.sync_status = "🟡 로컬 변경사항 대기 중"

        st.session_state.last_sync_time = time.time()
    except Exception:
        st.session_state.sync_status = "🔴 동기화 실패"

def handle_note_change(direction, db_idx):
    note_key = f"note_{direction}_{db_idx}"
    note = st.session_state.get(note_key, "").strip()
    ds = get_dir_state(direction)
    ds["notes"][str(db_idx)] = note
    token = st.session_state.get("token")
    if token and st.session_state.get("authenticated"):
        save_note_to_db(token, direction, db_idx, note)

def handle_slider_change(direction, db_idx, key):
    touch_key = f"{direction}_{db_idx}_{key}"
    st.session_state.touched_sliders[touch_key] = True
    st.session_state.show_toast = True

    # Get value from slider key
    slider_key = f"slider_{direction}_{db_idx}_{key}"
    score = st.session_state.get(slider_key, SCORE_MIN)

    # 1. Update local session scores in memory (0ms lag UI response)
    ds = get_dir_state(direction)
    db_idx_str = str(db_idx)
    if db_idx_str not in ds["scores"]:
        ds["scores"][db_idx_str] = {}
    ds["scores"][db_idx_str][key] = score

    # 2. Queue pending update with timestamp for debounced batch flush
    st.session_state.pending_updates[(direction, db_idx, key)] = {
        "direction": direction,
        "sentence_id": db_idx,
        "model_name": key,
        "score": score,
        "timestamp": time.time()
    }

    # 3. Transition status to pending local changes
    st.session_state.sync_status = "🟡 로컬 변경사항 대기 중"

def sync_jump_input(direction, ds):
    """Keep the '문장 번호로 이동' number input in sync with Prev/Next navigation."""
    key = f"jump_input_{direction}"
    if key in st.session_state:
        st.session_state[key] = ds["index_ptr"] + 1

def handle_jump_input_change(direction):
    key = f"jump_input_{direction}"
    ds = get_dir_state(direction)
    value = st.session_state.get(key, 1)
    target_ptr = max(0, min(int(value) - 1, len(ds["session_indices"]) - 1))
    go_to_ptr(direction, target_ptr)

def next_sentence(direction):
    flush_pending_ratings(force=True)
    ds = get_dir_state(direction)
    db = all_databases[direction]
    candidate_keys = candidate_keys_by_direction[direction]
    if not ds["session_indices"]:
        return
    ptr = ds["index_ptr"]
    s_idx = ds["session_indices"][ptr]
    db_idx = db[s_idx].get("original_index", s_idx)

    # Check if all candidates for the current sentence are rated/touched
    all_rated = True
    for k in candidate_keys:
        touch_key = f"{direction}_{db_idx}_{k}"
        if not st.session_state.get("touched_sliders", {}).get(touch_key, False):
            all_rated = False
            break

    if all_rated:
        if ds["index_ptr"] < len(ds["session_indices"]) - 1:
            ds["index_ptr"] += 1
            new_s_idx = ds["session_indices"][ds["index_ptr"]]
            new_db_idx = db[new_s_idx].get("original_index", new_s_idx)
            ds["shuffled_candidates"].pop(new_db_idx, None)
        st.session_state.show_warning = False
    else:
        st.session_state.show_warning = True
    sync_jump_input(direction, ds)

def prev_sentence(direction):
    flush_pending_ratings(force=True)
    ds = get_dir_state(direction)
    db = all_databases[direction]
    if not ds["session_indices"]:
        return
    if ds["index_ptr"] > 0:
        ds["index_ptr"] -= 1
        new_s_idx = ds["session_indices"][ds["index_ptr"]]
        new_db_idx = db[new_s_idx].get("original_index", new_s_idx)
        ds["shuffled_candidates"].pop(new_db_idx, None)
    st.session_state.show_warning = False
    sync_jump_input(direction, ds)

def go_to_ptr(direction, ptr):
    flush_pending_ratings(force=True)
    ds = get_dir_state(direction)
    db = all_databases[direction]
    if not ds["session_indices"]:
        return
    if 0 <= ptr < len(ds["session_indices"]):
        ds["index_ptr"] = ptr
        new_s_idx = ds["session_indices"][ptr]
        new_db_idx = db[new_s_idx].get("original_index", new_s_idx)
        ds["shuffled_candidates"].pop(new_db_idx, None)
    st.session_state.show_warning = False
    sync_jump_input(direction, ds)

# Main structure
st.markdown("<h3 style='text-align: center; margin-top: -0px; margin-bottom: 15px; font-weight: bold;'>제주어-표준어 번역 평가</h3>", unsafe_allow_html=True)

# Check if admin is active via query parameter
is_admin_query = st.query_params.get("admin") == ADMIN_PASSWORD

# --- SIDEBAR CONTROL PANEL ---
with st.sidebar:
    st.header("⚙️ 설정 패널")

    st.subheader("🌐 평가 방향")
    direction_options = list(DIRECTIONS.keys())
    selected_direction = st.radio(
        "평가할 방향을 선택하세요:",
        options=direction_options,
        format_func=lambda k: DIRECTIONS[k]["label"],
        index=direction_options.index(st.session_state.direction),
        key="direction_radio",
        label_visibility="collapsed",
    )
    if selected_direction != st.session_state.direction:
        flush_pending_ratings(force=True)
        st.session_state.direction = selected_direction
        st.rerun()
    st.markdown("---")

    current_direction = st.session_state.direction
    dir_cfg = DIRECTIONS[current_direction]
    database = all_databases[current_direction]
    total_sentences = len(database)
    candidate_keys = candidate_keys_by_direction[current_direction]
    ds = get_dir_state(current_direction)

    # Evaluator Identity
    if st.session_state.get("authenticated") and st.session_state.get("token"):
        st.subheader("🙋 평가자")
        st.write(f"**{st.session_state.token}**(으)로 참여 중입니다.")
        st.caption("같은 번호를 다시 선택하면 이어서 진행할 수 있어요.")

        # Status Indicator Badge
        status_text = st.session_state.get("sync_status", "🟢 데이터베이스와 동기화됨")
        st.markdown("**데이터베이스 동기화 상태:**")
        st.info(f"{status_text}")
        st.markdown("---")

    # Check periodic auto-sync flush (>0.8s window)
    flush_pending_ratings(force=False)

    # Admin Access Passcode
    st.subheader("🔑 관리자 접근")
    admin_passcode = st.text_input("암호를 입력하세요:", type="password", help="암호를 입력하면 평가 대시보드에 접근할 수 있습니다.")
    is_admin = is_admin_query or (admin_passcode == ADMIN_PASSWORD)

    st.markdown("---")

    # Determine mode and show options based on admin status
    if is_admin:
        app_mode = st.radio("앱 모드", ["📝 문장 평가", "📊 분석 대시보드", "🔍 데이터베이스 찾아보기"])
    else:
        app_mode = "📝 문장 평가"
        st.info("🔒 관리자 암호를 입력하면 대시보드에 접근할 수 있습니다.")

    if total_sentences > 0:
        # Scoring Progress in current session
        session_size = len(ds["session_indices"])
        session_rated_count = 0
        for s_idx in ds["session_indices"]:
            item = database[s_idx]
            db_idx = item.get("original_index", s_idx)
            db_idx_str = str(db_idx)
            if db_idx_str in ds["scores"]:
                scores_dict = ds["scores"][db_idx_str]
                # Count as rated only if all candidate keys have an actual selection (not None)
                if all(scores_dict.get(k) is not None for k in candidate_keys):
                    session_rated_count += 1
        session_completion_pct = (session_rated_count / session_size) * 100 if session_size > 0 else 0

        st.subheader("진행 상황")
        st.write(f"평가 완료: **{session_rated_count}** / {session_size} ({session_completion_pct:.1f}%)")
        st.progress(session_completion_pct / 100.0)

        # Jump to sentence by number (session scope)
        st.markdown("---")
        st.subheader("🎯 빠른 이동")
        jump_key = f"jump_input_{current_direction}"
        if jump_key not in st.session_state:
            st.session_state[jump_key] = ds["index_ptr"] + 1
        st.number_input(
            "문장 번호로 이동:",
            min_value=1,
            max_value=session_size,
            step=1,
            key=jump_key,
            label_visibility="collapsed",
            on_change=handle_jump_input_change,
            args=(current_direction,),
        )

    # Save and Download Panel - ONLY shown to admin
    if is_admin:
        st.markdown("---")
        st.subheader("💾 내보내기 및 데이터 관리")

        # Flush any pending local changes before building export data
        flush_pending_ratings(force=True)

        # Pull records exclusively for active evaluator token (all directions)
        current_tok = st.session_state.get("token", "")
        token_rows = load_ratings_rows_by_token(current_tok) if current_tok else []
        export_dict = {}
        for token, row_direction, s_idx, model, score in token_rows:
            export_dict.setdefault(token, {}).setdefault(row_direction, {}).setdefault(str(s_idx), {})[model] = score

        # Download JSON
        json_scores = json.dumps(export_dict, indent=2, ensure_ascii=False)
        st.download_button(
            label="📥 내 점수 다운로드 (JSON)",
            data=json_scores,
            file_name=f"jejueo_scores_{current_tok}.json" if current_tok else "jejueo_scores.json",
            mime="application/json",
            use_container_width=True
        )

        # Download CSV
        if token_rows:
            rows = []
            for token, row_direction, s_idx, model, score in token_rows:
                rows.append({
                    "평가자": token,
                    "방향": DIRECTIONS.get(row_direction, {}).get("label", row_direction),
                    "문장번호": s_idx,
                    "모델명": model,
                    "점수": score,
                    "원문": db_by_original_index.get(row_direction, {}).get(s_idx, {}).get("source", ""),
                })
            df_export = pd.DataFrame(rows)
            csv_scores = df_export.to_csv(index=False, encoding='utf-8-sig')
            st.download_button(
                label="📥 내 점수 다운로드 (CSV)",
                data=csv_scores,
                file_name=f"jejueo_scores_{current_tok}.csv" if current_tok else "jejueo_scores.csv",
                mime="text/csv",
                use_container_width=True
            )

        # Reset ratings
        st.markdown("<br><br>", unsafe_allow_html=True)
        if st.button("⚠️ 모든 방향의 점수 초기화", type="secondary", use_container_width=True):
            flush_pending_ratings(force=True)
            delete_ratings_by_token(st.session_state.token)
            st.session_state.dir_state = {}
            st.session_state.touched_sliders = {}
            for k in list(st.session_state.keys()):
                if k.startswith("slider_"):
                    del st.session_state[k]
            st.toast("점수가 초기화되었습니다!", icon="✅")
            st.rerun()

# --- MAIN CONTENT AREA ---

if total_sentences == 0:
    st.info(f"`{dir_cfg['path']}` 파일에 올바른 문장 데이터가 있는지 확인해주세요.")

# Mode 1: Rating Interface
elif app_mode == "📝 문장 평가":
    ptr = ds["index_ptr"]
    s_idx = ds["session_indices"][ptr]
    current_item = database[s_idx]
    db_idx = current_item.get("original_index", s_idx)
    session_size = len(ds["session_indices"])

    # Show warning at the top of navigation (Next button is nearby)
    if st.session_state.get("show_warning", False):
        st.warning("아직 평가하지 않은 후보 문장이 있습니다. 모두 평가한 후 다시 진행해주세요!")

    # Navigation buttons layout - compact text size
    col_prev, col_num, col_next = st.columns([1, 2, 1])
    with col_prev:
        st.button("⏮️ 이전", on_click=prev_sentence, args=(current_direction,), disabled=(ptr == 0), use_container_width=True)
    with col_num:
        if is_admin:
            st.markdown(f"<div style='text-align: center; font-weight: bold; font-size: 1.1rem; margin-top: 5px;'>문장 {ptr + 1} / {session_size} (DB 번호: #{db_idx})</div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div style='text-align: center; font-weight: bold; font-size: 1.1rem; margin-top: 5px;'>문장 {ptr + 1} / {session_size}</div>", unsafe_allow_html=True)
    with col_next:
        st.button("다음 ⏭️", on_click=next_sentence, args=(current_direction,), disabled=(ptr == session_size - 1), use_container_width=True)

    # Rating Guidelines Expander
    with st.expander("📖 평가 지침 보기", expanded=False):
        st.markdown(f"""
        **아래 각 후보 문장이 원문의 의미를 얼마나 정확하고 자연스럽게 담고 있는지 0~100점 사이로 평가해주세요.**

        - **0점**: 원문의 의미와 전혀 관련이 없거나 이해할 수 없는 문장
        - **100점**: 원문의 의미를 완벽하고 자연스럽게 담고 있는 문장

        이 평가는 WMT(Workshop on Machine Translation)의 **직접 평가(Direct Assessment, DA)** 방식을 따릅니다.
        문법이나 어휘 선택 하나하나보다는, **의미 전달의 정확성과 자연스러움**을 종합적으로 고려하여 점수를 매겨주세요.

        각 문장 아래에는 **특이사항**을 적을 수 있는 칸이 있습니다. 번역이 이상하거나, 원문 자체가 어색하거나,
        점수로 표현하기 애매한 부분 등 눈에 띄는 점이 있으면 편하게 적어주세요. (선택사항이며, 비워두셔도 됩니다)

        *현재 평가 방향: **{dir_cfg['label']}***
        """)

    # Display Source in clean container
    st.markdown(f"""
    <div class="source-container">
        <div class="container-title" style="color: #FF9800;">{dir_cfg['source_label']}</div>
        <div>{escape_html_display(current_item.get('source', ''))}</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<hr style='margin:10px 0;' />", unsafe_allow_html=True)

    # Stable shuffle management for Blind Rating
    if BLIND_RATING:
        if db_idx not in ds["shuffled_candidates"]:
            # Shuffle the keys for this index and save them
            shuffled_keys = candidate_keys.copy()
            random.shuffle(shuffled_keys)
            ds["shuffled_candidates"][db_idx] = shuffled_keys
        display_order = ds["shuffled_candidates"][db_idx]
    else:
        display_order = candidate_keys

    # Retrieve existing scores for the current sentence
    existing_item_scores = ds["scores"].get(str(db_idx), {})

    # Initialize touched status for the current sentence
    for k in candidate_keys:
        touch_key = f"{current_direction}_{db_idx}_{k}"
        if k in existing_item_scores and touch_key not in st.session_state.touched_sliders:
            st.session_state.touched_sliders[touch_key] = True

    # Column headers for Candidate and Score columns
    col_hdr_left, col_hdr_right = st.columns([6.5, 3.5], gap="medium")
    with col_hdr_left:
        st.markdown(f"<span style='font-size: 0.9rem; font-weight: bold; color: var(--text-color);'>🔍 {dir_cfg['candidate_label']} 문장</span>", unsafe_allow_html=True)
    with col_hdr_right:
        st.markdown("<div style='text-align: right; padding-right: 15px; font-size: 0.85rem; font-weight: bold; color: var(--text-color);'>📊 점수 (0~100), 높을수록 좋음</div>", unsafe_allow_html=True)

    # Render candidate rows inside standard bordered containers
    updated_item_scores = {}
    for rank, key in enumerate(display_order):
        candidate_text = current_item.get(key, "*(비어 있음)*")
        ordinal = KOREAN_ORDINALS[rank] if rank < len(KOREAN_ORDINALS) else str(rank + 1)
        display_name = f"{dir_cfg['candidate_label']} {ordinal}" if BLIND_RATING else f"모델: {key}"
        existing_score = existing_item_scores.get(key, SCORE_MIN)

        slider_key = f"slider_{current_direction}_{db_idx}_{key}"
        if slider_key not in st.session_state:
            st.session_state[slider_key] = existing_score

        container_key = f"container_{current_direction}_{db_idx}_{key}"
        with st.container(border=True, key=container_key):
            col_text, col_rating = st.columns([6.5, 3.5], gap="medium")
            with col_text:
                st.markdown(f"<div class='container-title' style='color: #2196F3; margin-bottom: 2px;'>{display_name}</div>", unsafe_allow_html=True)
                st.markdown(escape_html_display(candidate_text), unsafe_allow_html=True)
            with col_rating:
                score = st.slider(
                    label=f"{display_name} 평가",
                    min_value=SCORE_MIN,
                    max_value=SCORE_MAX,
                    step=1,
                    key=slider_key,
                    label_visibility="collapsed",
                    on_change=handle_slider_change,
                    args=(current_direction, db_idx, key)
                )
        updated_item_scores[key] = score

    # Optional per-sentence note (not tied to any single candidate)
    st.markdown("<hr style='margin:10px 0;' />", unsafe_allow_html=True)
    st.markdown("<span style='font-size: 0.9rem; font-weight: bold; color: var(--text-color);'>📝 특이사항 (선택사항)</span>", unsafe_allow_html=True)
    st.caption("번역이 이상하거나, 원문이 어색하거나, 그 밖에 눈에 띄는 점이 있으면 자유롭게 적어주세요.")
    note_key = f"note_{current_direction}_{db_idx}"
    if note_key not in st.session_state:
        st.session_state[note_key] = ds["notes"].get(str(db_idx), "")
    st.text_area(
        "이 문장에 대한 특이사항:",
        key=note_key,
        placeholder="이 문장에서 특별히 눈에 띄는 점이 있으면 자유롭게 적어주세요. (평가 제출과 무관하며, 비워두셔도 됩니다)",
        label_visibility="collapsed",
        on_change=handle_note_change,
        args=(current_direction, db_idx),
    )

    # Collect and inject custom CSS for touched sliders to turn them green
    touched_css_rules = []
    for k in candidate_keys:
        touch_key = f"{current_direction}_{db_idx}_{k}"
        slider_key = f"slider_{current_direction}_{db_idx}_{k}"
        container_key = f"container_{current_direction}_{db_idx}_{k}"
        is_touched = st.session_state.get("touched_sliders", {}).get(touch_key, False)
        if is_touched and slider_key in st.session_state:
            val = st.session_state[slider_key]
            pct = int(val)
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
        st.toast("평가가 저장되었습니다!", icon="💾")
        st.session_state.show_toast = False

    # Quick Save indicator
    if is_admin:
        st.caption(f"✓ 현재 문장 #{db_idx} 점수: { {k: v for k, v in updated_item_scores.items()} }")
    else:
        st.caption("✓ 평가가 로컬에 저장되었습니다. '다음'을 눌러 제출하세요.")

# Mode 2: Analytics Dashboard
elif app_mode == "📊 분석 대시보드":
    st.subheader("📊 평가 분석 대시보드")

    all_rows = load_all_ratings_from_db()
    if not all_rows:
        st.info("아직 수집된 평가가 없습니다. 먼저 문장을 평가해주세요!")
    else:
        # Prepare data
        scores_list = []
        for token, row_direction, s_idx, model, score in all_rows:
            scores_list.append({
                "평가자": token,
                "방향": DIRECTIONS.get(row_direction, {}).get("label", row_direction),
                "문장번호": s_idx,
                "모델": model,
                "점수": score
            })
        df = pd.DataFrame(scores_list)

        # Evaluator assignment / collision check: since each token's group is
        # derived from a hash (not a fixed roster), two evaluators can land in
        # the same group by chance. Surface that here so it can be caught early.
        st.markdown("### 👥 평가자 배정 현황")
        distinct_tokens = sorted(df["평가자"].unique())
        group_to_tokens = {}
        for tok in distinct_tokens:
            group_to_tokens.setdefault(group_index_for_token(tok), []).append(tok)

        assignment_df = pd.DataFrame(
            [{"아이디": tok, "배정 그룹": group_index_for_token(tok)} for tok in distinct_tokens]
        ).sort_values("배정 그룹")
        st.dataframe(assignment_df, use_container_width=True, hide_index=True)

        collisions = {g: toks for g, toks in group_to_tokens.items() if len(toks) > 1}
        if collisions:
            for g, toks in sorted(collisions.items()):
                st.warning(
                    f"⚠️ 그룹 {g}번에 {len(toks)}명이 겹쳐 있습니다: {', '.join(toks)} — "
                    "같은 문장을 중복으로 보게 됩니다. 겹치는 분 중 한 명은 다른 아이디로 다시 시작해주세요."
                )
        else:
            st.success("✅ 지금까지 참여한 평가자들 간에 배정 그룹 겹침이 없습니다.")

        missing_groups = [g for g in range(NUM_GROUPS) if g not in group_to_tokens]
        if missing_groups:
            st.info(f"아직 데이터가 없는 그룹: {', '.join(str(g) for g in missing_groups)}")

        st.markdown("---")

        # Optional direction filter for analytics
        direction_filter_options = ["전체"] + [cfg["label"] for cfg in DIRECTIONS.values()]
        direction_filter = st.selectbox("방향 필터:", direction_filter_options)
        if direction_filter != "전체":
            df = df[df["방향"] == direction_filter]

        if df.empty:
            st.info("선택한 방향에 대한 평가 데이터가 없습니다.")
        else:
            # KPI Metrics
            total_rated_sentences = df["문장번호"].nunique()

            col_kpi1, col_kpi2, col_kpi3 = st.columns(3)
            with col_kpi1:
                st.metric("평가된 문장 수", f"{total_rated_sentences} / {total_sentences}")
            with col_kpi2:
                overall_avg = df["점수"].mean()
                st.metric("전체 평균 점수", f"{overall_avg:.2f} / 100")
            with col_kpi3:
                model_with_highest_avg = df.groupby("모델")["점수"].mean().idxmax()
                highest_avg_score = df.groupby("모델")["점수"].mean().max()
                st.metric("최고 평균 모델", f"{model_with_highest_avg}", f"{highest_avg_score:.2f}점")

            st.markdown("---")

            col_chart1, col_chart2 = st.columns(2)

            with col_chart1:
                st.markdown("### 🏆 모델별 평균 점수")
                avg_scores = df.groupby("모델")["점수"].mean().reset_index().sort_values(by="점수", ascending=False)
                st.bar_chart(avg_scores.set_index("모델"), y="점수", color="#FF4B4B")

                st.dataframe(
                    avg_scores.rename(columns={"점수": "평균 점수"}).style.format({"평균 점수": "{:.2f}"}),
                    use_container_width=True
                )

            with col_chart2:
                st.markdown("### 📈 모델별 점수 분포")
                pivot_df = df.pivot_table(index="점수", columns="모델", aggfunc="size", fill_value=0)
                st.line_chart(pivot_df)

                st.markdown("#### 모델 성능 지표")
                stats_df = df.groupby("모델")["점수"].agg(["count", "mean", "std", "min", "median", "max"]).reset_index()
                stats_df.columns = ["모델", "평가 수", "평균 점수", "표준편차", "최소", "중앙값", "최대"]
                st.dataframe(
                    stats_df.style.format({
                        "평균 점수": "{:.2f}",
                        "표준편차": "{:.2f}"
                    }),
                    use_container_width=True,
                    hide_index=True
                )

            st.markdown("---")
            st.markdown("### 🧐 모델 간 의견 차이 (표준편차 상위)")
            st.write("아래는 모델 간 점수 편차(표준편차)가 가장 큰 문장들입니다. 정성적 분석에 유용합니다.")

            # Calculate standard deviation of scores per sentence index (within selected direction scope)
            disagreement = df.groupby(["방향", "문장번호"])["점수"].std().reset_index()
            disagreement.columns = ["방향", "문장번호", "점수 표준편차"]
            top_disagreement = disagreement.sort_values(by="점수 표준편차", ascending=False).head(5)

            direction_label_to_key = {cfg["label"]: d for d, cfg in DIRECTIONS.items()}
            for rank, (_, row) in enumerate(top_disagreement.iterrows()):
                row_direction_label = row["방향"]
                row_direction_key = direction_label_to_key.get(row_direction_label)
                s_idx = int(row["문장번호"])
                std_val = row["점수 표준편차"]
                item = db_by_original_index.get(row_direction_key, {}).get(s_idx, {})

                sentence_df = df[(df["방향"] == row_direction_label) & (df["문장번호"] == s_idx)]
                avg_ratings = sentence_df.groupby("모델")["점수"].mean().to_dict()

                st.markdown(f"#### #{rank+1}. [{row_direction_label}] 문장 번호 {s_idx} (점수 표준편차: {std_val:.2f})")
                st.markdown(f"**원문**: {item.get('source', '')}")

                cols = st.columns(len(avg_ratings))
                for c_idx, (model_name, avg_score) in enumerate(avg_ratings.items()):
                    with cols[c_idx]:
                        st.metric(label=model_name, value=f"{avg_score:.2f}/100")
                st.markdown("<hr style='margin:10px 0; border:0; border-top:1px dashed #ccc;' />", unsafe_allow_html=True)

# Mode 3: Browse Database
elif app_mode == "🔍 데이터베이스 찾아보기":
    st.subheader("🔍 데이터베이스 찾아보기")
    st.write(f"'{dir_cfg['label']}' 방향의 전체 문장과 평가 결과를 확인할 수 있습니다.")

    browse_data = []
    for i, item in enumerate(database):
        orig_idx = item.get("original_index", i)
        has_rated = "예" if str(orig_idx) in ds["scores"] else "아니오"
        row = {
            "번호": orig_idx,
            "평가 여부": has_rated,
            "원문": item.get("source", ""),
        }
        if str(orig_idx) in ds["scores"]:
            for key in candidate_keys:
                row[f"점수 ({key})"] = ds["scores"][str(orig_idx)].get(key, "")
        else:
            for key in candidate_keys:
                row[f"점수 ({key})"] = ""
        row["특이사항"] = ds["notes"].get(str(orig_idx), "")
        browse_data.append(row)

    df_browse = pd.DataFrame(browse_data)

    # Filter options
    filter_rated = st.selectbox("평가 필터:", ["전체 문장", "평가 완료만", "미평가만"])
    if filter_rated == "평가 완료만":
        df_filtered = df_browse[df_browse["평가 여부"] == "예"]
    elif filter_rated == "미평가만":
        df_filtered = df_browse[df_browse["평가 여부"] == "아니오"]
    else:
        df_filtered = df_browse

    # Search functionality
    search_query = st.text_input("🔍 문장 검색:")
    if search_query:
        df_filtered = df_filtered[df_filtered["원문"].str.contains(search_query, case=False, na=False)]

    st.write(f"{len(df_filtered)} 건의 기록이 있습니다.")
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
