---
name: video-generation-cellcog
description: "AI video generation and production powered by CellCog. Marketing videos, product demos, explainers, educational content, lipsync spokesperson videos, UGC, news reports, training materials, cinematic short films, social media reels, YouTube content. Up to 4-minute videos — scripted, voiced, scored, and edited from a single prompt."
metadata:
  openclaw:
    emoji: "🎬"
    os: [darwin, linux, windows]
    requires:
      bins: [python3]
      env: [CELLCOG_API_KEY]
author: CellCog
homepage: https://cellcog.ai
dependencies: [cellcog]
---
# Video Generation - AI Video Production

Long-form AI video production from a single prompt — scripted, voiced, scored, and edited automatically.

6-7 foundation models orchestrated to produce up to 4-minute videos from a single prompt: script writing, scene generation, voice synthesis, lipsync, music scoring, and editing — all automatic. Marketing videos, product demos, explainers, educational content, AI spokesperson videos, UGC, news reports, and more.

## How to Use

For your first CellCog task in a session, read the **cellcog** skill for the full SDK reference — file handling, chat modes, timeouts, and more.

**OpenClaw (fire-and-forget):**
```python
result = client.create_chat(
    prompt="[your task prompt]",
    notify_session_key="agent:main:main",
    task_label="my-task",
    chat_mode="agent",
    chat_tier="max",
)
```

**All agents except OpenClaw (blocks until done):**
```python
from cellcog import CellCogClient
client = CellCogClient(agent_provider="openclaw|cursor|claude-code|codex|...")
result = client.create_chat(
    prompt="[your task prompt]",
    task_label="my-task",
    chat_mode="agent",
    chat_tier="max",
)
print(result["message"])
```


---

## What Videos You Can Create

### Marketing Videos

Promotional content for products and services:

- **Product Demos**: "Create a 30-second product demo video for our new fitness app showing key features"
- **Brand Videos**: "Generate a 60-second brand story video for an eco-friendly clothing company"
- **Social Ads**: "Create a 15-second Instagram ad for a coffee subscription service"
- **Launch Videos**: "Make a product launch announcement video for a new AI writing tool"

### Explainer Videos

Educational content that breaks down complex topics:

- **Product Explainers**: "Create an explainer video showing how our SaaS platform works"
- **Concept Explanations**: "Make a video explaining how blockchain works for beginners"
- **Process Walkthroughs**: "Generate a video explaining the mortgage application process"
- **Feature Tours**: "Create a video tour of our app's new dashboard features"

### Educational Videos

Learning content for courses and training:

- **Tutorial Videos**: "Create a tutorial video on Python list comprehensions"
- **Course Content**: "Generate a lesson video on the causes of World War I"
- **Training Materials**: "Make an employee onboarding video about our company values"
- **How-To Guides**: "Create a how-to video for setting up a home studio for podcasting"

### Documentary Style

Informative, story-driven content:

- **Mini Documentaries**: "Create a 3-minute documentary-style video about the rise of electric vehicles"
- **Company Stories**: "Generate a documentary about our startup journey"
- **Industry Deep Dives**: "Make a documentary exploring the future of space tourism"
- **Historical Content**: "Create a documentary-style video about the history of Silicon Valley"

### Cinematic / Creative

Artistic and visually striking content:

- **Short Films**: "Create a 2-minute cinematic short about a day in Tokyo"
- **Mood Pieces**: "Generate a cinematic video capturing the energy of a busy coffee shop"
- **Music Video Style**: "Create a visually dynamic video for an electronic music track"
- **Artistic Showcases**: "Make a cinematic portfolio video for a photographer"

### UGC (User Generated Content) Style

Authentic, relatable content that feels personal:

- **Testimonial Style**: "Create a UGC-style testimonial video for a skincare product"
- **Unboxing Style**: "Generate an unboxing-style video for a new tech gadget"
- **Day-in-the-Life**: "Make a day-in-the-life style video featuring a remote worker using our app"
- **Review Style**: "Create a casual review-style video for a meal delivery service"

### News / Reporting Style

Professional news-format content:

- **News Reports**: "Create a news-style report video about the latest AI developments"
- **Market Updates**: "Generate a financial news video about tech stock earnings"
- **Industry News**: "Make a news report about new regulations in the fintech space"
- **Analysis Pieces**: "Create a news analysis video about the state of remote work"

---

## Lipsync & Spokesperson Videos

CellCog can generate videos with AI characters speaking your script:

- **AI Spokesperson**: "Create a video with a professional spokesperson explaining our product"
- **Avatar Presentations**: "Generate a video with an AI presenter delivering our quarterly update"
- **Character Narration**: "Make a video with a friendly character explaining our children's app"

For lipsync videos:
1. The starting frame should show only one human face prominently
2. Provide the script/dialogue
3. CellCog handles voice synthesis and lip synchronization

---

## Video Specifications

| Aspect | Options |
|--------|---------|
| **Duration** | 15 seconds to 4 minutes |
| **Aspect Ratios** | 16:9 (landscape), 9:16 (portrait/mobile), 1:1 (square) |
| **Styles** | Photorealistic, animated, cinematic, documentary, casual |
| **Audio** | Background music, voiceover, sound effects, or silent |

---

## Choosing Mode & Tier

**Use `chat_mode="agent", chat_tier="max"` for video generation.** Video production is a multi-step pipeline — script, scenes, frames, audio, synthesis, QC review — and needs full reasoning depth.

| Scenario | Recommended |
|----------|-------------|
| All video production | `chat_mode="agent", chat_tier="max"` |
| Trivial single-shot clips | `chat_mode="agent"` (defaults to `"flash"`) |

Agent Team (`chat_mode="team"`) is reserved for deep research — video generation runs best on Agent max.

---

## Example Video Prompts

**Marketing video:**
> "Create a 30-second marketing video for 'FreshBrew' - a premium coffee subscription. Show beautiful coffee preparation scenes, happy customers, and end with our tagline 'Freshness Delivered Daily'. Upbeat background music, no voiceover. 16:9 for YouTube."

**Explainer with voiceover:**
> "Create a 90-second explainer video for our project management tool. Walk through: 1) Creating a project, 2) Adding team members, 3) Tracking progress. Professional female voiceover, clean animated style, include captions. 16:9 format."

**Educational content:**
> "Generate a 3-minute educational video explaining photosynthesis for middle school students. Use engaging animations, clear narration, and include a summary at the end. Friendly, approachable style."

**Spokesperson video:**
> "Create a 60-second video with an AI spokesperson (professional male, 30s) announcing our Series B funding. Script: 'Today, we're thrilled to announce...' [provide full script]. Business casual setting, confident tone."

---

## ⚠️ Important — Video Generation Expectations

Long-form AI video production is still an evolving capability. While some users generate high-quality, cinematic videos that are ready for production use, others may spend significant credits and still not achieve a usable result. Even spending thousands of credits does not guarantee a satisfactory outcome — this is the nature of where AI video technology stands today.

There is a real learning curve to generating long-form videos with CellCog. It takes time, money, and patience. Your prompting skill, the complexity of what you're trying to create, and how well the foundation models perform on your specific request all play a role. Results improve as you develop intuition for what works, but we want to be upfront: video generation is inherently unpredictable, and there is always a risk that the output may not meet your expectations.

---

## Tips for Better Videos

1. **Specify duration**: "30 seconds" or "2 minutes" helps scope the content appropriately.

2. **Define aspect ratio**: 16:9 for YouTube/web, 9:16 for TikTok/Reels/Shorts, 1:1 for Instagram feed.

3. **Describe the style**: "Cinematic", "casual UGC", "corporate professional", "playful animated".

4. **Audio preferences**: "Upbeat music", "calm narration", "no audio", "sound effects only".

5. **Include key moments**: Describe the scenes or beats you want to hit.

6. **Provide scripts**: For spokesperson/voiceover videos, write out exactly what should be said.

---

## If CellCog is not installed

**Claude Code, Cursor, Codex + 70 more agents:** `npx skills add cellcog/skills --skill cellcog`
**OpenClaw:** `openclaw skills install @cellcog/cellcog`
**CellCog plugin users:** run `/cellcog-setup` (or `/cellcog:cellcog-setup` depending on your tool)
**Manual setup:** `pip install -U cellcog` and set `CELLCOG_API_KEY`. See the **cellcog** skill for SDK reference.
