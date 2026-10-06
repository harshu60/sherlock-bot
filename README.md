# 🕵️‍♂️ Sherlock Bot

A context-aware, persona-driven Discord bot built in Python. Sherlock combines modern conversational LLMs with persistent vector embeddings to maintain semantic memory across Discord servers.

---

## 📌 Overview

Most standard chat bots treat every interaction as an isolated session. **Sherlock** solves this by implementing semantic retrieval memory:
* **Persona Handling:** Emulates the analytical demeanor and deduction style of Sherlock Holmes.
* **Vector Memory:** Uses ChromaDB to index, retrieve, and reference past guild interactions semantically rather than relying strictly on raw text buffers.
* **Asynchronous Design:** Built on `discord.py` to handle concurrent user interactions and asynchronous API requests efficiently.

---

## 🛠️ Tech Stack & Architecture

| Component | Technology | Purpose |
| :--- | :--- | :--- |
| **Language** | Python 3.10+ | Core bot logic & async event loop |
| **Framework** | `discord.py` | Discord API wrapper & event handlers |
| **LLM Provider** | DeepSeek API | High-speed, cost-effective language generation |
| **Vector Database**| ChromaDB | Semantic embeddings & long-term conversation retrieval |
| **Deployment** | Linux / DigitalOcean | Cloud droplet VPS running continuous background processes |

---

## 🚀 Key Features

* **Per-Guild Memory Isolation:** Separates message embeddings by server context to prevent data leakage between communities.
* **Semantic Retrieval (RAG-inspired):** Queries ChromaDB for contextually relevant past interactions before dispatching prompts to the LLM.
* **Robust Error Handling:** Catches API rate limits, connection dropouts, and empty token responses gracefully to ensure bot uptime.
* **Structured Prompts:** Enforces rigid character alignment and logical deductions without excessive token overhead.

---

## 📂 Project Structure

```text
sherlock-bot/
├── bot.py             # Discord bot, commands, and message events
├── config.py          # Environment-backed application configuration
├── memory.py          # Per-server ChromaDB conversation memory
├── settings.py        # Persistent per-server channel settings
├── sherlock.py        # DeepSeek response and prompt service
└── requirements.txt   # Project dependencies
```

The runtime is organized around small objects with one responsibility:
`SherlockBot` coordinates Discord events, `SherlockService` generates replies,
`ConversationMemory` owns vector storage, and `ServerSettings` owns JSON
configuration. Run the application with `python bot.py`.

### Discord token setup

Set `DISCORD_BOT_TOKEN` in `.env` to the token from the **Bot** page of the
same application whose bot is invited to the server:

```dotenv
DISCORD_BOT_TOKEN=your_bot_token
```

Use the token value itself; do not include the `Bot ` prefix. If startup fails
with `Improper token has been passed`, regenerate the bot token in the Discord
Developer Portal, replace the value in `.env`, and restart the process. A
previous token is invalidated when it is regenerated.
