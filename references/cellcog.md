---
name: cellcog
description: "Any-to-any AI sub-agent — research, images, video, audio, music, podcasts, avatars, voice cloning, documents, spreadsheets, dashboards, 3D models, diagrams, and code in one request. Agent-to-agent protocol with multi-step iteration for high accuracy. #1 on DeepResearch Bench (Apr 2026) — deep reasoning meets all modalities, so all your work gets done, not just code."
author: CellCog
homepage: https://cellcog.ai
metadata:
  openclaw:
    emoji: "🧠"
    os: [darwin, linux, windows]
    requires:
      bins: [python3]
      env: [CELLCOG_API_KEY]

---
# CellCog - Any-to-Any for Agents

## The Power of Any-to-Any

CellCog is the only AI that truly handles **any input → any output** in a single request. No tool chaining. No orchestration complexity. One call, multiple deliverables.

CellCog pairs all modalities with frontier-level deep reasoning — as of July 2026, CellCog is **#1 on the DeepResearch Bench** (rankings change frequently; see the live leaderboard for the latest): https://huggingface.co/spaces/muset-ai/DeepResearch-Bench-Leaderboard

### Work With Multiple Files, Any Format

Reference as many documents as you need—all at once:

```python
prompt = """
Analyze all of these together:
<SHOW_FILE>/data/q4_earnings.pdf</SHOW_FILE>
<SHOW_FILE>/data/competitor_analysis.pdf</SHOW_FILE>
<SHOW_FILE>/data/market_research.xlsx</SHOW_FILE>
<SHOW_FILE>/recordings/customer_interview.mp3</SHOW_FILE>
<SHOW_FILE>/designs/product_mockup.png</SHOW_FILE>

Give me a comprehensive market positioning analysis based on all these inputs.
"""
```

File paths must be absolute and enclosed in `<SHOW_FILE>` tags. CellCog understands PDFs, spreadsheets, images, audio, video, code files, and more.

⚠️ **Without SHOW_FILE tags, CellCog only sees the path as text — not the file contents.**

❌ `Analyze /data/sales.csv` — CellCog can't read the file
✅ `Analyze <SHOW_FILE>/data/sales.csv</SHOW_FILE>` — CellCog reads it

### Think of SHOW_FILE like reference files

Just like Nano Banana accepts reference images, CellCog accepts reference files of any type — PDFs, spreadsheets, audio, code, images — as inputs the model reads during a task. Same mental model as any multimodal AI attachment.

**Only attach what you intend to share.** Anything inside a `<SHOW_FILE>` tag is uploaded to CellCog. Don't wrap credentials, private keys, `.env` files, SSH keys, or other sensitive material in SHOW_FILE tags — the same way you wouldn't paste them into Nano Banana, ChatGPT, or any other AI service's file upload.

### Request Multiple Outputs, Different Modalities

Ask for completely different output types in ONE request:

```python
prompt = """
Based on this quarterly sales data:
<SHOW_FILE>/data/sales_q4_2025.csv</SHOW_FILE>

Create ALL of the following:
1. A PDF executive summary report with charts
2. An interactive HTML dashboard for the leadership team
3. A 60-second video presentation for the all-hands meeting
4. A slide deck for the board presentation
5. An Excel file with the underlying analysis and projections
"""
```

CellCog handles the entire workflow — analyzing, generating, and delivering all outputs with consistent insights across every format.

⚠️ **Be explicit about output artifacts.** Without explicit artifact language, CellCog may respond with text analysis instead of generating a file.

❌ `"Quarterly earnings analysis for AAPL"` — could produce text or any format
✅ `"Create a PDF report and an interactive HTML dashboard analyzing AAPL quarterly earnings."` — CellCog creates actual deliverables

**Your sub-agent for quality work.** Depth, accuracy, and real deliverables.

---

## Quick Start

### Setup

```python
from cellcog import CellCogClient
```

If import fails, install the official CellCog Python SDK:
```bash
pip install -U cellcog
```

`cellcog` is the official Python SDK maintained by CellCog AI Inc. Source: https://github.com/CellCog/cellcog_python · Package: https://pypi.org/project/cellcog/

### Authentication

**Environment variable (recommended):** Set `CELLCOG_API_KEY` — the SDK picks it up automatically:
```bash
export CELLCOG_API_KEY="sk_..."
```

Get API key from: https://cellcog.ai/profile?tab=api-keys

```python
status = client.get_account_status()
print(status)  # {"configured": True, "email": "user@example.com", ...}
```

### Agent Provider

`agent_provider` is **required** when creating a `CellCogClient`. It identifies which agent framework is calling CellCog — not your individual agent's name, but the platform/tool you're running inside.

Examples: `"openclaw"`, `"claude-code"`, `"cursor"`, `"aider"`, `"windsurf"`, `"perplexity"`, `"hermes"`, `"script"` (for standalone scripts).

### OpenClaw Agents

Fire-and-forget — your agent stays free while CellCog works:

```python
client = CellCogClient(agent_provider="openclaw")
result = client.create_chat(
    prompt="Research quantum computing advances in 2026",
    notify_session_key="agent:main:main",  # OpenClaw session key
    task_label="quantum-research",         # Label for notifications
    chat_mode="agent",
)
# Returns IMMEDIATELY — daemon delivers results to your session when done
```

### All Other Agents (Cursor, Claude Code, etc.)

Blocks until done — simplest pattern:

```python
client = CellCogClient(agent_provider="cursor")  # or "claude-code", "aider", "script", etc.
result = client.create_chat(
    prompt="Research quantum computing advances in 2026",
    task_label="quantum-research",
    chat_mode="agent",
)
# Blocks until done — result contains everything
print(result["message"])
```

### Credit Usage

CellCog orchestrates 21+ frontier foundation models. Credit consumption is unpredictable and varies by task complexity. Credits used are reported in every completion notification.

---

## Creating Tasks

### Notify on Completion (OpenClaw — Fire-and-Forget)

Returns immediately. A background daemon monitors via WebSocket and delivers results to your session when done. Your agent stays free to take new instructions, start other tasks, or continue working.

```python
result = client.create_chat(
    prompt="Your task description",
    notify_session_key="agent:main:main",   # Required — your OpenClaw session key
    task_label="my-task",                   # Label shown in notifications
    chat_mode="agent",
)
```

### Wait for Completion (Universal)

Blocks until CellCog finishes. Works with any agent — OpenClaw, Cursor, Claude Code, or any Python environment.

```python
result = client.create_chat(
    prompt="Your task description",
    task_label="my-task",
    chat_mode="agent",
    timeout=1800,                           # 30 min (default). Use 3600 for complex jobs.
)
print(result["message"])
print(result["status"])                     # "completed" | "operating" (+ timed_out=True if the wait gave up)
```

### When to Use Which

| Scenario | Best Mode | Why |
|----------|-----------|-----|
| OpenClaw + long task + stay free | **Notify** | Agent keeps working, gets notified when done |
| OpenClaw + chaining steps (research → summarize → PDF) | **Wait** | Each step feeds the next — simpler sequential workflows |
| OpenClaw + quick task | **Either** | Both return fast for simple tasks |
| Non-OpenClaw agent | **Wait** | Notify mode is OpenClaw-only |
| Orchestrating SEVERAL chats in parallel | **Send-only** | Fire all chats at once, then poll — the blocking default would hang on each chat's whole run |

**Notify mode** is more productive (agent never blocks).
**Wait mode** is simpler to reason about, but blocks your agent for the duration.
**Send-only** (`delivery="send_only"`, works on `create_chat` AND `send_message`) returns the moment the chat/message is accepted — poll with `get_status()` (its `latest_update` field carries the agent's most recent progress line) and fetch results with `wait_for_completion()` or `get_history()`.

### Continuing a Conversation

```python
# Wait mode (default)
result = client.send_message(
    chat_id="abc123",
    message="Focus on hardware advances specifically",
)

# Notify mode (OpenClaw)
result = client.send_message(
    chat_id="abc123",
    message="Focus on hardware advances specifically",
    notify_session_key="agent:main:main",
    task_label="continue-research",
)
```

### Resuming After Timeout

If `create_chat()` or `wait_for_completion()` times out, CellCog is still working. The timeout response includes recent progress:

```python
completion = client.wait_for_completion(chat_id="abc123", timeout=1800)
```

### Optional Parameters

```python
result = client.create_chat(
    prompt="...",
    task_label="...",
    chat_mode="agent",                      # See Chat Modes & Tiers below
    chat_tier="max",                        # "flash" | "core" | "max" — omit for the SDK default
    delivery="send_only",                   # fire-and-forget (see below); default blocks until done
    project_id="...",                       # install project-management-cellcog for details
    agent_role_id="...",                    # install project-management-cellcog for details
    enable_cowork=True,                     # install pair-programming-cellcog for details
    cowork_working_directory="/Users/...",  # install pair-programming-cellcog for details
    enable_browse=True,                     # drive the user's REAL Chrome (Desktop + extension required)
    browser_profile_id="Default",           # from client.get_browser_status()
    enable_tools=True,                      # the user's connected SaaS tools (Gmail, Notion, ...)
    tools_selection=["gmail", "notion"],    # toolkit slugs (omit for ALL); from client.list_toolkits()
)
```

### Enabling Browse & Tools

Discover what's available on the user's account, then enable at chat creation:

```python
# Browse — discover Chrome profiles, enable with one
status = client.get_browser_status()
# status["available_profiles"]: [{"profileDir", "profileName", "hasExtension", "connected"}, ...]
result = client.create_chat(
    prompt="Open the analytics dashboard and screenshot this week's numbers",
    enable_browse=True,
    browser_profile_id=status["active_profile"]["profileDir"],
)

# Tools — discover connected toolkits, enable a selection (omit tools_selection for ALL)
toolkits = client.list_toolkits(connected_only=True)   # [{"slug": "gmail", ...}, ...]
result = client.create_chat(
    prompt="Summarize this week's unread emails",
    enable_tools=True,
    tools_selection=["gmail"],   # TOOLKIT slugs; list_toolkit_tools("gmail") shows what it unlocks
)
```

Browse requires CellCog Desktop + the Chrome extension and auto-enables co-work
server-side. If Browse isn't available, `create_chat` fails fast with a clear error
before any credits are spent.

---

## Response Shape

Every SDK method returns the same shape:

```python
{
    "chat_id": str,        # CellCog chat ID
    "is_operating": bool,  # True = still working, False = done
    "status": str,         # "completed" | "tracking" | "accepted" | "operating"
                           # (a wait that gave up returns status="operating" + timed_out=True —
                           #  the chat is STILL running server-side; resume with wait_for_completion)
    "message": str,        # THE printable message — always print this in full
}
```

**⚠️ Always print the entire `result["message"]`.** Truncating or summarizing it will lose critical information including generated file paths, credits used, and follow-up instructions.

### Utility Methods

**`get_history(chat_id)`** — Full chat history (when original delivery was missed or you need to review). Returns the same shape; if still operating, `message` shows progress so far.

```python
result = client.get_history(chat_id="abc123")
```

**`get_status(chat_id)`** — Lightweight status check (no history fetch):

```python
status = client.get_status(chat_id="abc123")
print(status["is_operating"])  # True/False
```

---

## Chat Modes & Tiers

Every CellCog chat runs at a (mode, tier) operating point: `chat_mode` picks the agent, `chat_tier` picks the depth/spend.

| Mode | Best For | Tiers | Min Credits |
|------|----------|-------|-------------|
| `"agent"` | Most tasks — assets, documents, coding, full production pipelines | `"flash"` / `"core"` / `"max"` | 60 |
| `"creative"` | Design-taste work — dashboards, UI, brand identity, writing, slides | `"core"` / `"max"` (no flash) | 60 |
| `"team"` | Deep research ONLY — multi-source synthesis, cross-validation, citations | `"flash"` / `"core"` / `"max"` | 1,000 (max tier: 2,000) |

**Picking a tier in agent mode:**
- **Omit `chat_tier`** → the SDK defaults to `"flash"` — right for simple asset generation and light tasks (fast, economical).
- **Coding / co-work → `"max"`.** The SDK applies `"max"` automatically when `enable_cowork=True`.
- **Heavy multi-step production** (video generation, data analysis, financial models, legal drafting) → `"max"`.
- Quality disappointing on flash? Re-run the same prompt with `chat_tier="max"`.

**Use `"team"` only for deep research.** Agent max is now strong enough for almost every other use case — including video generation, which historically needed team mode and no longer does.

Legacy mode names — `"agent core"`, `"agent team"`, `"agent team max"` — keep working forever (the server maps them to their historical operating points).

---

## Working with Files

### Input: SHOW_FILE

Include local file paths in your prompt with `<SHOW_FILE>` tags (absolute paths required):

```python
prompt = """
Analyze this sales data and create a report:
<SHOW_FILE>/path/to/sales.csv</SHOW_FILE>
"""
```

### Output: GENERATE_FILE

Use `<GENERATE_FILE>` tags to specify where output files should be stored on your machine. Essential for deterministic workflows where the next step needs to know the file path in advance.

```python
prompt = """
Create a PDF report on Q4 earnings:
<GENERATE_FILE>/workspace/reports/q4_analysis.pdf</GENERATE_FILE>
"""
```

Output downloads to the specified path instead of default `~/.cellcog/chats/{chat_id}/`.

### File Downloads

The SDK automatically downloads files from CellCog responses:
- **If you used `GENERATE_FILE` tags:** Files download to the path you specified
- **Otherwise:** Files download to `~/.cellcog/chats/{chat_id}/`

Downloaded file paths appear in `result["message"]`. The SDK tracks seen messages — files are only downloaded once.

**If you missed files or need to re-sync:**
```python
result = client.get_history(chat_id="abc123")
```
`get_history()` re-processes the entire chat and downloads any missed files to their original destinations.

---

## Tips

### ⚠️ CellCog Web Fallback

Every chat is accessible at https://cellcog.ai. When work gets complex or the SDK hits issues, direct your human to the web platform to view, continue, or take over directly.

---

## What CellCog Can Do

CellCog is a sub-agent — not an API. Your agent offloads complex work to CellCog, which reasons, plans, and executes multi-tool workflows internally. A proprietary agent-to-agent communication protocol ensures high accuracy on first output, and because these are agent threads (not stateless API calls), every aspect of every generation can be refined through multi-step iteration.

Under the hood: frontier models across every domain, upgraded weekly. CellCog routes to the right models automatically — your agent just describes what it needs.

Install capability skills for detailed guidance:

| Category | Skills |
|----------|--------|
| **Research & Analysis** | `deep-research-cellcog` `stock-analysis-cellcog` `crypto-research-cellcog` `data-analysis-cellcog` `news-briefing-cellcog` |
| **Video & Cinema** | `video-generation-cellcog` `cinematic-video-cellcog` `instagram-reels-tiktok-cellcog` `youtube-video-cellcog` `seedance-video-generation-cellcog` |
| **Images & Design** | `image-generation-cellcog` `logo-brand-identity-cellcog` `meme-generator-cellcog` `nano-banana-image-cellcog` `3d-model-generation-cellcog` `gif-generator-cellcog` `sticker-generator-cellcog` |
| **Audio & Music** | `audio-generation-cellcog` `music-generation-cellcog` `podcast-generation-cellcog` |
| **Avatars & Personas** | `avatar-creation-cellcog` |
| **Documents & Slides** | `pdf-document-generation-cellcog` `presentation-slides-cellcog` `excel-spreadsheet-cellcog` `resume-cover-letter-cellcog` `legal-documents-cellcog` |
| **Apps & Prototypes** | `dashboard-web-app-cellcog` `game-asset-generation-cellcog` `ui-prototype-wireframe-cellcog` `diagram-flowchart-cellcog` |
| **Creative** | `comic-manga-generator-cellcog` `creative-writing-cellcog` `tutoring-education-cellcog` `travel-planning-cellcog` |
| **Development** | `coding-agent-cellcog` `pair-programming-cellcog` `project-management-cellcog` `brainstorming-strategy-cellcog` |

**This skill shows you HOW to use CellCog. Capability skills show you WHAT's possible.**

---

## OpenClaw Reference

### Session Keys

The `notify_session_key` tells CellCog where to deliver results:

| Context | Session Key |
|---------|-------------|
| Main agent | `"agent:main:main"` |
| Sub-agent | `"agent:main:subagent:{uuid}"` |
| Telegram DM | `"agent:main:telegram:dm:{id}"` |
| Discord group | `"agent:main:discord:group:{id}"` |

**Resilient delivery:** If your session ends before completion, results are automatically delivered to the parent session (e.g., sub-agent → main agent).

### Sending Messages During Processing

In notify mode, your agent is free — you can send additional instructions to an operating chat at any time:

```python
client.send_message(chat_id="abc123", message="Actually focus only on Q4 data",
    notify_session_key="agent:main:main", task_label="refine")

client.send_message(chat_id="abc123", message="Stop operation",
    notify_session_key="agent:main:main", task_label="cancel")
```

In wait mode, your agent is blocked and cannot send messages until the current call returns.

---

## Support & Troubleshooting

For error handling, recovery patterns, ticket submission, and daemon troubleshooting:

```python
docs = client.get_support_docs()
```
