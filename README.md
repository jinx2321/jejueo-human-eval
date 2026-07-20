# 📝 LLM Sentence Scorer

![Python Version](https://img.shields.io/badge/Python-3.10%2B-blue.svg)
![Framework](https://img.shields.io/badge/Framework-Streamlit-FF4B4B.svg)
![Database](https://img.shields.io/badge/Database-PostgreSQL%20%2F%20SQLAlchemy-336791.svg)
![CI/CD Pipeline](https://img.shields.io/badge/CI%2FCD-GitHub%20Actions-green.svg)

**LLM Sentence Scorer** is a web-based blind human evaluation platform designed for Large Language Model (LLM) text restructuring and sentence generation tasks. It enables evaluators to quantitatively score outputs across multiple candidate models (including 10M, 100M, Llama_Simple, Llama_Preserve, Llama_FewShot, OpenAI, and Reference) while automatically persisting ratings to a serverless PostgreSQL cloud database.

---

## ✨ Key Features

### 🔐 1. Two-Gate Access Control & Session Persistence
- **Gate 1: Classroom Activation Protection**
  - Protected by a classroom password (`TUM2026`) to block unauthorized bot traffic.
  - **10-Minute HMAC URL Refresh Token**: Generates an HMAC-SHA256 signed URL token upon activation. Evaluators reloading or refreshing the browser (`F5`) within 10 minutes bypass password re-entry automatically.
- **Gate 2: Evaluator Token Branching**
  - **Seamless Reconnection**: Reconnect with a 6-character token to restore historical evaluation progress across devices.
  - **Anonymous New Evaluator**: Instantly generate a fresh, unique 6-character evaluator token.

### 🎲 2. Blind Rating Engine
- **Shuffled Display Order**: Candidate model names are hidden and their display order is randomized per sentence to eliminate evaluation bias.
- **Four-Dimensional Rating Scale (0–10)**:
  1. 🎯 **Faithfulness**: Preserves original source sentence meaning without adding, omitting, or distorting information.
  2. ✍️ **Grammaticality**: Fluent, natural, and free of syntax or spelling errors.
  3. 🔄 **Syntactic Structuring**: Restructures the syntactic frame rather than copying original grammar.
  4. 🔀 **Lexical Diversity**: Uses diverse vocabulary and synonyms instead of repeating exact source words.

### 📋 3. Token-Scoped Data Export & Corpus Protection
- **Token-Scoped Export**: Download rating data in JSON and CSV formats. Exported data is strictly filtered to the active evaluator token (`st.session_state.token`), safeguarding data privacy.
- **Corpus Anti-Copy & Token Selection**: Context menu (right-click) and text selection are disabled on core evaluation sentences to protect dataset integrity, while text selection and one-click copying are explicitly enabled for evaluator tokens.

### 📊 4. Admin Analytics Dashboard
- Unlock via admin passcode (`admin` password or `?admin=admin` URL parameter):
  - **KPI Metrics**: Coverage rate, overall average rating, and top-performing model metrics.
  - **Performance Charts**: Average score bar charts, rating distribution line charts, and statistical summary tables (Std Dev, Min, Median, Max).
  - **Model Disagreement Ranking**: Identifies sentences with the highest score standard deviation across models for qualitative analysis.
  - **Database Search**: Search source and reference sentences across the entire corpus.

---

## 📂 Repository Structure

```text
llm_score/
├── app.py                         # Main Streamlit application (2-Gate auth, rating UI, dashboard, SQL session)
├── sampling.py                    # Dataset sampling script (fixed seed 42 sampling 100 entries)
├── central_database.json          # Master sentence corpus
├── evaluation_batch_100.json      # Static 100-sentence evaluation batch
├── requirements.txt               # Project dependencies
├── tests/
│   └── test_app.py                # Pytest unit test suite (compilation, JSON schema, HMAC validation)
└── .github/
    └── workflows/
        ├── ci.yml                 # GitHub Actions CI workflow (linting, schema checks, pytest)
        └── auto_pr.yml            # Automated Pull Request workflow (gh CLI integration)
```

---

## 🚀 Quick Start

### 1. Clone Repository & Setup Environment
```bash
git clone https://github.com/huhan606/llm-score.git
cd llm-score

# Create and activate a virtual environment (optional)
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt pytest
```

### 3. Database Secrets Configuration (Optional)
Configure PostgreSQL connection settings in `.streamlit/secrets.toml`:
```toml
[connections.sql]
dialect = "postgresql"
host = "your-database-host.neon.tech"
port = 5432
database = "neondb"
username = "your_user"
password = "your_password"
sslmode = "require"
```

### 4. Launch Streamlit Application
```bash
streamlit run app.py
```
The web app will automatically open in your browser at `http://localhost:8501`.

---

## 🧪 Testing & CI/CD Pipeline

### Local Test Execution
Run the automated test suite locally:
```bash
pytest tests/test_app.py -v
```
Tests cover:
- `test_python_syntax_compilation`: Validates compilation of `app.py` and `sampling.py`.
- `test_evaluation_batch_json_validity`: Validates `evaluation_batch_100.json` structure, entry count (100), and key schemas (including `OpenAI`).
- `test_hmac_token_*`: Validates HMAC signature generation, expiration checks, and tamper prevention.

### CI/CD Workflows
- **CI Pipeline (`ci.yml`)**: Automatically triggers on `push` and `pull_request` to validate Python syntax, JSON schema integrity, and execute pytest.
- **Auto-PR (`auto_pr.yml`)**: Pushing a `feature/**` branch automatically opens a Pull Request into `main` via `gh CLI`.
- **Streamlit Cloud CD**: Merges into `main` automatically trigger production deployment on Streamlit Community Cloud.

---

## 🛡️ Git Workflow & Contributions

This project follows standard Git Feature Branch practices:
1. Create a feature branch from `main`: `git checkout -b feature/your-feature-name`
2. Commit with conventional messages: `git commit -m "feat(scope): detailed description"`
3. Push branch to GitHub: `git push -u origin feature/your-feature-name`
4. Automated CI & Auto-PR will validate and create a PR for code review into `main`.
