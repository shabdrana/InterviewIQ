# InterviewIQ — API and design setup

## 1. Install and run (Windows PowerShell)

```powershell
cd interviewiq
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
streamlit run app.py
```

## 2. Connect an AI API

The app already has an API provider layer in `core/llm.py`. It supports Anthropic directly and OpenAI-compatible chat-completions endpoints. It does not need a separate backend server for the current single-process Streamlit version.

For Gemini, open Google AI Studio and create an API key. Put the key in `.env` as `OPENAI_API_KEY`, then use:

```dotenv
LLM_PROVIDER=openai
OPENAI_API_KEY=YOUR_GEMINI_API_KEY
OPENAI_MODEL=gemini-2.5-flash
OPENAI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
```

For OpenAI, use your OpenAI API key, `OPENAI_MODEL=gpt-4o-mini`, and `OPENAI_BASE_URL=https://api.openai.com/v1`.

For Groq, use your Groq API key, a model enabled in your Groq account, and `OPENAI_BASE_URL=https://api.groq.com/openai/v1`.

Restart Streamlit after changing `.env`. Then sign in → Settings → AI engine & rubric → Test connection. A successful connection means the app can reach the model. If no key is configured, the app still works in clearly labelled rule-based mode.

**Important:** API usage may cost money depending on provider and account. Never paste your key into Python source, GitHub, screenshots, or chat. `.env` is ignored by Git. Rotate a key immediately if it is exposed.

## 3. UI changes in this update

- Animated ambient background glow and subtle page/card entrance motion.
- Floating interview preview panel with orbit animation, live indicator, and animated answer-quality bar.
- Updated landing-page headline and feature cues.
- Reduced-motion accessibility support so animations stop when a device requests reduced motion.

## 4. Before public deployment

This is currently a Streamlit + SQLite prototype. For a public multi-user launch, add proper deployment secrets, HTTPS, rate limiting, stronger session/authentication controls, database backups, and move SQLite to PostgreSQL. Change `MENTOR_ACCESS_CODE` from the example value. Do not commit `.env` or the local database.
