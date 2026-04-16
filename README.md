# LogIQ — AI Root Cause Analyzer

> **Paste logs. Get the root cause, explanation, fix, and prevention — in seconds.**

LogIQ is an AI-powered Root Cause Analysis (RCA) tool built with Streamlit and Google Gemini. It analyzes raw system logs and returns structured, engineer-grade output: what broke, why it broke, how to fix it, and how to prevent it from happening again.

---

## Screenshot

```
┌─────────────────────────────────────────────────────┐
│  🔍 LogIQ          [Analyzer] [History] [Docs]      │
├─────────────────────────────────────────────────────┤
│  Stop Guessing. Find the Root Cause in Seconds.     │
├──────────────────┬──────────────────────────────────┤
│  Paste Logs      │  🔴 High Severity  ⚡ 94%         │
│  [log viewer]    │  Root Cause  ─────────────────   │
│  [Analyze →]     │  Explanation ─────────────────   │
│                  │  Solution │ Prevention           │
├──────────────────┴──────────────────────────────────┤
│  ✦ AI Follow-up Assistant  │  How to use            │
└─────────────────────────────────────────────────────┘
```

---

## Features

| Feature | Description |
|---|---|
| 🧠 **Root Cause Detection** | AI pinpoints the exact failure from raw log data |
| 📖 **Plain English Explanation** | No jargon — clear summary of what broke and why |
| 🛠️ **Actionable Fix** | Step-by-step solution tailored to the specific error |
| 🛡️ **Prevention Strategy** | Monitoring tips and best practices to avoid recurrence |
| 📁 **File Upload** | Upload `.log`, `.txt`, `.csv` files directly |
| ⬇️ **Download Report** | Export full analysis as a `.txt` report |
| 🎨 **Log Highlighting** | Color-coded log viewer (ERROR=red, WARN=yellow, INFO=blue) |
| 💬 **AI Chatbot** | Context-aware follow-up assistant |
| 📂 **History** | Last 20 analyses stored per session |
| 📘 **Docs** | Built-in documentation tab |

---

## Tech Stack

- **Frontend** — [Streamlit](https://streamlit.io)
- **AI Engine** — [openai]
- **Language** — Python 3.9+
- **Fonts** — Plus Jakarta Sans, Fira Code

---

## Project Structure

```
logiq/
├── app.py              ← Main Streamlit UI (all pages + features)
├── rca_engine.py       ← openai API call + log analysis logic
├── prompts.py          ← Prompt engineering templates
├── utils.py            ← Log cleaning utilities
├── requirements.txt    ← Python dependencies
├── .env                ← API keys — NEVER commit this file
├── .gitignore          ← Excludes .env and other sensitive files
└── README.md           ← This file
```

---

## Setup & Installation

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/logiq.git
cd logiq
```

### 2. Create a virtual environment (recommended)

```bash
python -m venv venv
source venv/bin/activate        # Linux / macOS
venv\Scripts\activate           # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Get a OPENROUTER_API_KEY

1. Go to [https://openrouter.ai/](https://openrouter.ai/openai/gpt-oss-120b:free)
2. Click **Create API Key**
3. Copy the key

### 5. Create your `.env` file

Create a file named `.env` in the project root:

```env
OPENROUTER_API_KEY=your_gemini_api_key_here
```

> ⚠️ **Never commit this file.** It is already excluded via `.gitignore`.

### 6. Run the app

```bash
streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501) in your browser.

---

## Usage

### Basic Analysis

1. Open the **Analyzer** tab
2. Paste your raw logs into the text box (or upload a `.log` / `.txt` file)
3. Click **Analyze Logs →**
4. View the structured result: Severity, Root Cause, Explanation, Solution, Prevention
5. Click **Download Full Report** to save a `.txt` file

### Follow-up Questions

Use the **AI Follow-up Assistant** at the bottom to ask context-aware questions:
- *"Show me the fix as a bash command"*
- *"Is this a known CVE?"*
- *"How do I add monitoring for this?"*
- *"Explain this error to a junior developer"*

### History

Click the **History** tab to view and re-download your last 20 analyses (stored per session).

---

## Supported Log Formats

LogIQ works with any plain-text log format, including:

- Python tracebacks
- Nginx / Apache access & error logs
- Docker and Kubernetes logs
- Java / Spring stack traces
- PostgreSQL / MySQL error logs
- Node.js / Express logs
- Systemd journal logs
- AWS CloudWatch logs
- GitHub Actions logs
- Any `[LEVEL] timestamp message` format

---

## API Key Security

| ✅ Safe | ❌ Not Safe |
|---|---|
| Store key in `.env` | Hardcode key in `app.py` or any `.py` file |
| Add `.env` to `.gitignore` | Commit `.env` to Git |
| Use `python-dotenv` to load | Share key in chat or email |


---

## Uploading to GitHub

### First time

```bash
git init
git add .
git commit -m "Initial commit: LogIQ AI RCA tool"
git branch -M main
git remote add origin https://github.com//YOUR_REPO.git
git push -u origin main
```

### After making changes

```bash
git add .
git commit -m "Your descriptive commit message"
git push
```

> ✅ Confirm `.env` is in your `.gitignore` before every push.

---

## What to Add Next (Roadmap)

| Feature | Difficulty | Description |
|---|---|---|
| Multi-file upload | Easy | Analyze multiple log files at once |
| Log source selector | Easy | Dropdown: Docker / Nginx / Python etc. for better prompting |
| Severity filter | Easy | Filter history by High / Medium / Low |
| Export as PDF | Medium | Generate a formatted PDF report |
| Slack / email alerts | Medium | Send analysis results to a Slack channel or email |
| Copy-to-clipboard | Easy | One-click copy for each section |
| Dark mode toggle | Easy | Switch between light and dark themes |
| Token counter | Easy | Show how many tokens were used per analysis |
| REST API endpoint | Medium | Expose `/analyze` endpoint via FastAPI for CI/CD integration |
| Auto-detect log type | Medium | Auto-classify log format before analysis |

---

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you'd like to change.

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

## Author

Built with ❤️ using Streamlit + open ai.