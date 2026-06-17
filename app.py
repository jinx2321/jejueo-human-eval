import streamlit as st
import json
import os
import pandas as pd
import random

# 1. Page Configuration and Theme Styling
st.set_page_config(
    page_title="LLM Sentence Scorer",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom clean CSS styles for a polished and minimal look
st.markdown("""
<style>
    /* Reduce Streamlit's default page top/bottom padding */
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 1rem !important;
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
</style>
""", unsafe_allow_html=True)

# 2. File Paths
DATABASE_PATH = "central_database.json"
SCORES_PATH = "scores.json"

# 3. Data Loading Functions
@st.cache_data
def load_database():
    """Load the central database of sentences."""
    if not os.path.exists(DATABASE_PATH):
        st.error(f"Error: Database file `{DATABASE_PATH}` not found in the current directory.")
        return []
    try:
        with open(DATABASE_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data
    except Exception as e:
        st.error(f"Error loading database: {str(e)}")
        return []

def load_scores():
    """Load existing scores from scores.json."""
    if os.path.exists(SCORES_PATH):
        try:
            with open(SCORES_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            st.warning(f"Failed to read `{SCORES_PATH}`. Initializing fresh scores. Error: {str(e)}")
    return {}

def save_scores(scores):
    """Save current scores to scores.json."""
    try:
        with open(SCORES_PATH, 'w', encoding='utf-8') as f:
            json.dump(scores, f, indent=2, ensure_ascii=False)
    except Exception as e:
        st.error(f"Failed to save scores: {str(e)}")

# Load data
database = load_database()
total_sentences = len(database)

# --- BACKEND CONFIGURATION ---
ADMIN_PASSWORD = "admin"
BLIND_RATING = True  # Hide model names and randomize candidate display order
SAMPLE_SIZE = 100    # Number of random sentences loaded per login session

# 4. State Initialization
if "scores" not in st.session_state:
    st.session_state.scores = load_scores()

if "session_indices" not in st.session_state and total_sentences > 0:
    # Randomly sample SAMPLE_SIZE sentences for this session
    sample_count = min(SAMPLE_SIZE, total_sentences)
    st.session_state.session_indices = random.sample(range(total_sentences), sample_count)
    
    # Set index pointer to first unrated sentence in this sample list, or 0
    st.session_state.index_ptr = 0
    for ptr, db_idx in enumerate(st.session_state.session_indices):
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

# 5. Session State Navigation Functions
def next_sentence():
    if "session_indices" in st.session_state and st.session_state.index_ptr < len(st.session_state.session_indices) - 1:
        st.session_state.index_ptr += 1
        db_idx = st.session_state.session_indices[st.session_state.index_ptr]
        st.session_state.shuffled_candidates.pop(db_idx, None)

def prev_sentence():
    if "session_indices" in st.session_state and st.session_state.index_ptr > 0:
        st.session_state.index_ptr -= 1
        db_idx = st.session_state.session_indices[st.session_state.index_ptr]
        st.session_state.shuffled_candidates.pop(db_idx, None)

def go_to_ptr(ptr):
    if "session_indices" in st.session_state and 0 <= ptr < len(st.session_state.session_indices):
        st.session_state.index_ptr = ptr
        db_idx = st.session_state.session_indices[ptr]
        st.session_state.shuffled_candidates.pop(db_idx, None)

# Main structure
st.markdown("<h3 style='text-align: center; margin-top: -70px; margin-bottom: 15px; font-weight: bold;'>Sentence Scorer</h3>", unsafe_allow_html=True)

if total_sentences == 0:
    st.info("Please make sure `central_database.json` contains valid sentence objects and is in the same directory.")
else:
    # Get model candidate keys dynamically from the first record
    # Exclude source and reference
    first_record = database[0]
    candidate_keys = [k for k in first_record.keys() if k not in ["source", "reference"]]

    # Check if admin is active via query parameter or passcode input
    is_admin_query = st.query_params.get("admin") == ADMIN_PASSWORD

    # --- SIDEBAR CONTROL PANEL ---
    with st.sidebar:
        st.header("⚙️ Control Panel")
        
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
        
        st.markdown("---")
        
        # Scoring Progress in current session
        session_size = len(st.session_state.session_indices)
        session_rated_count = sum(1 for db_idx in st.session_state.session_indices if str(db_idx) in st.session_state.scores)
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
            
            # Download JSON
            json_scores = json.dumps(st.session_state.scores, indent=2, ensure_ascii=False)
            st.download_button(
                label="📥 Download Scores (JSON)",
                data=json_scores,
                file_name="llm_scores.json",
                mime="application/json",
                use_container_width=True
            )
            
            # Download CSV
            if st.session_state.scores:
                rows = []
                for idx, model_scores in st.session_state.scores.items():
                    row = {"index": int(idx)}
                    row.update(model_scores)
                    i = int(idx)
                    if i < len(database):
                        row["source"] = database[i].get("source", "")
                        row["reference"] = database[i].get("reference", "")
                    rows.append(row)
                df_export = pd.DataFrame(rows)
                csv_scores = df_export.to_csv(index=False, encoding='utf-8-sig')
                st.download_button(
                    label="📥 Download Scores (CSV)",
                    data=csv_scores,
                    file_name="llm_scores.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            
            # Reset ratings
            st.markdown("<br><br>", unsafe_allow_html=True)
            if st.button("⚠️ Reset All Scores", type="secondary", use_container_width=True):
                st.session_state.scores = {}
                save_scores({})
                st.toast("All scores have been reset!", icon="✅")
                st.rerun()

    # --- MAIN CONTENT AREA ---
    
    # Mode 1: Rating Interface
    if app_mode == "📝 Rate Sentences":
        ptr = st.session_state.index_ptr
        db_idx = st.session_state.session_indices[ptr]
        current_item = database[db_idx]
        session_size = len(st.session_state.session_indices)
        
        # Navigation buttons layout - compact text size
        col_prev, col_num, col_next = st.columns([1, 2, 1])
        with col_prev:
            st.button("⏮️ Previous", on_click=prev_sentence, disabled=(ptr == 0), use_container_width=True)
        with col_num:
            st.markdown(f"<div style='text-align: center; font-weight: bold; font-size: 1.1rem; margin-top: 5px;'>Sentence {ptr + 1} / {session_size} (Database ID: #{db_idx})</div>", unsafe_allow_html=True)
        with col_next:
            st.button("Next ⏭️", on_click=next_sentence, disabled=(ptr == session_size - 1), use_container_width=True)
            
        # Display Source & Reference in clean containers
        col_src, col_ref = st.columns(2)
        with col_src:
            st.markdown(f"""
            <div class="source-container">
                <div class="container-title" style="color: #FF9800;">Source Sentence</div>
                <div>{current_item.get('source', '')}</div>
            </div>
            """, unsafe_allow_html=True)
        with col_ref:
            st.markdown(f"""
            <div class="reference-container">
                <div class="container-title" style="color: #4CAF50;">Reference Sentence</div>
                <div>{current_item.get('reference', '')}</div>
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
        
        # Render candidate rows using a highly space-efficient split column layout
        updated_item_scores = {}
        for rank, key in enumerate(display_order):
            candidate_text = current_item.get(key, "*(empty)*")
            display_name = f"Candidate {chr(65 + rank)}" if BLIND_RATING else f"Model: {key}"
            default_val = existing_item_scores.get(key, 5) # Default score is 5
            
            # Render each candidate row side-by-side: left for text, right for slider
            col_text, col_slider = st.columns([6, 2], gap="medium")
            with col_text:
                st.markdown(f"""
                <div class="candidate-container">
                    <div class="container-title" style="color: #2196F3;">{display_name}</div>
                    <div style="font-weight: 500; font-size: 0.95rem; line-height: 1.4;">{candidate_text}</div>
                </div>
                """, unsafe_allow_html=True)
            with col_slider:
                score = st.slider(
                    label=f"Score for {display_name}",
                    min_value=0,
                    max_value=10,
                    value=default_val,
                    step=1,
                    key=f"slider_{db_idx}_{key}",
                    label_visibility="collapsed"
                )
                updated_item_scores[key] = score

        # Save scores on change
        if str(db_idx) not in st.session_state.scores or st.session_state.scores[str(db_idx)] != updated_item_scores:
            st.session_state.scores[str(db_idx)] = updated_item_scores
            save_scores(st.session_state.scores)
            st.toast("Progress Saved Automatically!", icon="💾")

        # Quick Save indicator - compact format
        st.caption(f"✓ Autosaved Sentence #{db_idx} rating: { {k: v for k, v in updated_item_scores.items()} }")

    # Mode 2: Analytics Dashboard
    elif app_mode == "📊 Analytics Dashboard":
        st.subheader("📊 Evaluation Analytics Dashboard")
        
        if not st.session_state.scores:
            st.info("No ratings collected yet. Please rate some sentences first to view analytics!")
        else:
            # Prepare data
            scores_list = []
            for idx_str, model_scores in st.session_state.scores.items():
                for model, score in model_scores.items():
                    scores_list.append({
                        "Sentence Index": int(idx_str),
                        "Model": model,
                        "Score": score
                    })
            df = pd.DataFrame(scores_list)
            
            # KPI Metrics
            total_rated_sessions = len(st.session_state.scores)
            
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
                item = database[s_idx]
                item_ratings = st.session_state.scores.get(str(s_idx), {})
                
                st.markdown(f"#### #{rank+1}. Sentence Index {s_idx} (Score StdDev: {std_val:.2f})")
                st.markdown(f"**Source**: {item.get('source', '')}")
                st.markdown(f"**Reference**: {item.get('reference', '')}")
                
                # Present ratings table
                ratings_summary = pd.DataFrame([item_ratings]).T.rename(columns={0: "Score"})
                ratings_summary.index.name = "Model"
                
                # Show horizontal colored display
                cols = st.columns(len(ratings_summary))
                for c_idx, (model_name, s_row) in enumerate(ratings_summary.iterrows()):
                    with cols[c_idx]:
                        st.metric(label=model_name, value=f"{s_row['Score']}/10")
                st.markdown("<hr style='margin:10px 0; border:0; border-top:1px dashed #ccc;' />", unsafe_allow_html=True)

    # Mode 3: Browse Database
    elif app_mode == "🔍 Browse Database":
        st.subheader("🔍 Browse Database & Ratings")
        st.write("Browse all sentences from the database alongside their ratings.")
        
        browse_data = []
        for i, item in enumerate(database):
            has_rated = "Yes" if str(i) in st.session_state.scores else "No"
            row = {
                "Index": i,
                "Rated": has_rated,
                "Source": item.get("source", ""),
                "Reference": item.get("reference", ""),
            }
            # Add scores if rated
            if str(i) in st.session_state.scores:
                for key in candidate_keys:
                    row[f"Score ({key})"] = st.session_state.scores[str(i)].get(key, "")
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
