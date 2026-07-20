# 📝 LLM Sentence Scorer (大语言模型句子生成评估系统)

![Python Version](https://img.shields.io/badge/Python-3.10%2B-blue.svg)
![Framework](https://img.shields.io/badge/Framework-Streamlit-FF4B4B.svg)
![Database](https://img.shields.io/badge/Database-PostgreSQL%20%2F%20SQLAlchemy-336791.svg)
![CI/CD Pipeline](https://img.shields.io/badge/CI%2FCD-GitHub%20Actions-green.svg)

**LLM Sentence Scorer** 是一个为大语言模型（LLM）文本重构与生成任务设计的双盲盲测评估系统。该系统允许评估人员对多个候选模型（包括 10M, 100M, Llama_Simple, Llama_Preserve, Llama_FewShot, OpenAI 及 Reference）产生的句子进行多维度量化评分，并自动同步评分至 PostgreSQL 云数据库。

---

## ✨ 核心特性

### 🔐 1. 双门控访问控制 (Two-Gate Authentication)
- **Gate 1：课堂激活保护 (Classroom Activation)**
  - 采用预设激活密码（`TUM2026`）阻挡非授权访问。
  - **10 分钟 HMAC URL 令牌持久化**：解锁后生成带时间戳与 HMAC-SHA256 签名的 URL 令牌。用户在 10 分钟内刷新页面 (`F5`) 无需重复输入密码。
- **Gate 2：评估者身份断点重连 (Token Branching)**
  - **无缝重连**：使用系统生成的 6 位 Token 随时恢复跨设备历史评分进度。
  - **匿名新建**：一键生成全新的 6 位匿名 Token。

### 🎲 2. 双盲评估机制 (Blind Rating Engine)
- **随机打乱顺序**：隐藏模型真实名称，对候选句子进行随机盲测排序，避免评估偏见。
- **四大评分维度 (1-10 分)**：
  1. 🎯 **Faithfulness（忠实度）**：是否保留原句核心语义，无增删或扭曲信息。
  2. ✍️ **Grammaticality（语法正确性）**：语法是否通顺、自然、无拼写错误。
  3. 🔄 **Syntactic Structuring（句法重构度）**：是否对原句句法进行了结构调整。
  4. 🔀 **Lexical Diversity（词汇丰富度）**：是否使用了多样化同义词，而非机械重复原词。

### 📋 3. Token 专属数据导出与防复制保护
- **Token 专属导出**：支持导出 CSV 和 JSON 格式评分数据，下载内容**仅包含当前 Token 账号下的评分记录**，保障个人隐私与数据独立。
- **语料防护与 Token 复制**：禁用页面右键菜单与核心语料选中文本，同时针对 6 位 Token 框开放一键复制支持。

### 📊 4. 管理员分析仪表盘 (Analytics Dashboard)
- 输入管理员密码（`admin`）后可解锁全量分析看板：
  - **KPI 核心指标**：已被评估句子覆盖率、总体平均得分、榜首模型指标。
  - **模型对比图表**：平均分柱状图、得分分布折线图、详细统计表（Standard Deviation, Min, Median, Max）。
  - **争议句子分析 (Highest Discrepancy)**：自动计算各句子在不同模型间标准差，展示高争议评估样例。
  - **全量数据库检索**：支持按关键词搜索全量源句子与参考译文。

---

## 📂 项目结构

```text
llm_score/
├── app.py                         # Streamlit 主应用（包含 2-Gate 认证、评分界面、看板与数据库交互）
├── sampling.py                    # 评估数据集采样脚本（基于 Seed 42 采样 100 条样本）
├── central_database.json          # 原始全量评估语料库
├── evaluation_batch_100.json      # 静态抽样的 100 条盲测评估数据集
├── requirements.txt               # 项目依赖配置
├── tests/
│   └── test_app.py                # Pytest 单元测试集（语法编译、JSON Schema 校验、HMAC Token 测试）
└── .github/
    └── workflows/
        ├── ci.yml                 # GitHub Actions CI 工作流 (Lint, Schema Check, Pytest)
        └── auto_pr.yml            # 自动 Pull Request 创建工作流 (gh CLI 集成)
```

---

## 🚀 本地快速启动

### 1. 克隆仓库与环境准备
```bash
git clone https://github.com/huhan606/llm-score.git
cd llm-score

# 创建并激活虚拟环境 (可选)
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate
```

### 2. 安装依赖
```bash
pip install -r requirements.txt pytest
```

### 3. 配置数据库密码 (可选)
在 `.streamlit/secrets.toml` 中配置 PostgreSQL 数据库连接信息：
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

### 4. 运行 Streamlit 应用
```bash
streamlit run app.py
```
应用启动后，浏览器会自动打开 `http://localhost:8501`。

---

## 🧪 自动化测试与 CI/CD

本项目集成了完整的 **GitHub Actions CI/CD** 自动化流：

### 1. 本地运行单元测试
```bash
pytest tests/test_app.py -v
```
测试项包括：
- `test_python_syntax_compilation`: 核心 Python 文件编译校验。
- `test_evaluation_batch_json_validity`: 检查 `evaluation_batch_100.json` 包含 100 条完整记录及包含 OpenAI 等所有必要字段。
- `test_hmac_token_*`: HMAC 签名、时间戳过期与防篡改测试。

### 2. CI/CD 工作流
- **CI Pipeline (`ci.yml`)**：每次 Push 或提交 PR 时，自动运行代码编译、Schema 校验及 Pytest 测试。
- **Auto-PR (`auto_pr.yml`)**：推送 `feature/**` 分支时，GitHub Actions 通过官方 `gh CLI` 自动发起 Pull Request。
- **Streamlit Cloud CD**：代码合并至 `main` 分支后，Streamlit Community Cloud 自动完成云端部署更新。

---

## 🛡️ 许可证与贡献指南

本项目采用标准的 Git Feature Branch 开发流程：
1. 从 `main` 分支创建新特性分支：`git checkout -b feature/your-feature-name`
2. 提交规范的 Commit：`git commit -m "feat(scope): detailed description"`
3. 推送分支至 GitHub：`git push -u origin feature/your-feature-name`
4. 自动触发 CI 检查与 Auto-PR，审核通过后合并至 `main`。
