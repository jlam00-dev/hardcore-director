# Third-party notices

## 3.0 candidate production orchestration

`scripts/hc_workflow/`, `director_workflow.py`, `workflow_bridge.py` and `workflow_login.py` are original implementations under this package's MIT license. They call an installed official Dreamina CLI, the user's local MiniMax Design MCP, and published Feishu/Weixin interfaces. No vendor binary, authentication cache or private creative-Skill content is redistributed.

Optional Feishu SDK: [larksuite/oapi-sdk-python](https://github.com/larksuite/oapi-sdk-python/tree/0d9749a4728446a0ffa2e8374b37b5e1ce1cfd9c), MIT; PyPI 1.7.5 was checked. Weixin protocol reference: [Tencent/openclaw-weixin](https://github.com/Tencent/openclaw-weixin/tree/874637a0dbc24050f72d1385add4fc6170a2d726), version 2.4.10, whose LICENSE text is MIT. SDKs and the optional cryptography dependency are not bundled; their own distributions retain their licenses.

The adapter license does not make remote services free or authorize account access, material uploads, spending, or expanded message scope.

This package combines original routing instructions with attributed third-party Skill snapshots and adapted ideas. Inclusion does not change the original licenses.

## rc.7 creative collaboration

- Scene diagnosis and minimal rewriting: original adaptation of the workflows and checklists in [jtydhr88/screenwriting-skills](https://github.com/jtydhr88/screenwriting-skills). The preserved [MIT license](references/support/licenses/screenwriting-skills-MIT.md) and [NOTICE](references/support/licenses/screenwriting-skills-NOTICE.md) distinguish original material from quoted books, scripts, translations and other third-party excerpts. Those excerpts are not redistributed here. Package examples are newly written.
- Blocking, staging and coverage: original adaptation of [wuwangzhang1216/DirectorSKILL](https://github.com/wuwangzhang1216/DirectorSKILL/tree/c65ae0d14457053efb1e354c7e7f7e120d97fad1); [full MIT license](references/support/licenses/DirectorSKILL-MIT.md). Optional performance timing also draws on [kangarooking/director-skills](https://github.com/kangarooking/director-skills/tree/301e6e72199f28b8ea82cd48ff06ab9ae49d0ee5); [full MIT license](references/support/licenses/director-skills-MIT.md). User dialogue and established character facts take precedence over upstream examples.
- Storyboard handoff, frozen keyframes and reference readiness: adapted concepts from [zenstory-ai/drama-skills](https://github.com/zenstory-ai/drama-skills/tree/d8a9a9b5f5fa0e46dc2644d55879d1c984ff70e6), MIT, Copyright (c) 2026 drama-skills contributors; [full license](references/support/licenses/drama-skills-MIT.md). No upstream runtime, default platform slots, quoted examples or private project data is bundled.
- Audio cue, selected-take evidence and narrative edit handoff: original adaptations of [konradre/video-production-skills](https://github.com/konradre/video-production-skills/tree/cd92701fd52fbfa668f2247687b32d0f85506fda); [full MIT license](references/support/licenses/video-production-skills-MIT.md). Only planning and handoff ideas are used. Upstream paid-service calls, voice-cloning workarounds, automatic retiming/looping, uploads and publication paths are excluded.
- The creative project contract, dependency checks, zero-budget draft compiler and newly written example are package-original. They do not replace real media inspection, platform contracts or user approvals. Fixed source paths, commits and observation dates are recorded in the dependency manifest and the creative component audit.
- Three existing local methods receive explicitly marked compatibility boundaries: generic video prompting, sound prompting and character design. Original method text and attribution remain. The character reference uses its already-documented `watermark: false` option for generated prompt text; no existing image/video watermark is removed. Historical duration/audio/density tables do not override the user's locked brief or the current selected platform contract. These are package revisions, not claimed upstream releases.

## Exact or near-exact Skill snapshots

- `references/short-drama-writer.md` — `@ckchzh/short-drama-writer` v2.3.6, MIT-0, source: https://clawhub.ai/ckchzh/skills/short-drama-writer
- `references/story-cog.md` — reviewed `@cellcog/creative-writing-cellcog` v1.0.17 snapshot, MIT-0, source: https://clawhub.ai/cellcog/skills/creative-writing-cellcog ; package entry restrictions remain separate.
- `references/cellcog.md` — package-original service-boundary adapter informed by `@cellcog/cellcog` v2.0.26 (MIT-0), source: https://clawhub.ai/cellcog/skills/cellcog . This is not the full upstream Skill or an SDK installation; employee/co-work and unrelated external operations are not imported.
- `references/video-generation-cellcog.md` — reviewed `@cellcog/video-generation-cellcog` v1.0.19 snapshot, MIT-0, source: https://clawhub.ai/cellcog/skills/video-generation-cellcog ; no automatic task, upload or retry authorization is inherited.
- Other bundled or adapted modules are enumerated in `manifests/dependencies.json` and retain their original authorship and terms. The repository MIT license does not override a listed third-party license.

## Adapted concepts

- Product/software promo shot vocabulary: `Vincentwei1021/video-shotcraft`, reviewed source snapshot `1266a3ec4831289c4d893d42dd5102723658039a`, Apache-2.0, Copyright 2026 Wei Yihao. The adapted module identifies modifications, current fixed source cards and one explicitly historical compatibility recipe. Full license: [video-shotcraft-Apache-2.0.md](references/support/licenses/video-shotcraft-Apache-2.0.md). No audio, template screenshots, Gallery media, or third-party brand footage is distributed here; source-specific download/publication automation is excluded.
- Storyboard validation concepts: `eternityspring/shuohao-skills`, reviewed source snapshot `1084e66bc6063e472bde2567425a99dc6d6ebcff`, Apache-2.0, Copyright 2026 烁皓. The Python validator and local contract are original implementations, not copies of upstream runtime. [License](references/support/licenses/shuohao-Apache-2.0.md) and [NOTICE](references/support/licenses/shuohao-NOTICE.md) are preserved.
- Chinese editing snapshot: `op7418/Humanizer-zh`, MIT, fixed path commit `f4518a8eab97b8bfebc66a89d34320a89bef6930`; [full copyright and license](references/support/licenses/humanizer-zh-MIT.md).
- The updated ECC adaptation preserves the [ECC MIT copyright and license](references/support/licenses/ECC-MIT.md). Its linked native Fusion presets are external examples whose test claims belong to the upstream; they are not bundled or tested here.
- The Seedance adaptation preserves the [OSide MIT copyright and license](references/support/licenses/OSide-MIT.md). Provider-specific parameters do not override first-party schemas or other providers.

- Cross-model prompt routing and Seedance reference-role discipline: `Square-Zero-Labs/video-prompting-skill`, Apache-2.0, https://github.com/Square-Zero-Labs/video-prompting-skill
- Storyboard packaging and continuity checks: `agentara/skills`, MIT, https://github.com/agentara/skills
- Seedance 2.5 staging, reference exclusions and job-splitting patterns: `OSideMedia/higgsfield-ai-prompt-skill`, MIT, https://github.com/OSideMedia/higgsfield-ai-prompt-skill
- Video editing workflow: `affaan-m/ECC`, MIT, https://github.com/affaan-m/ECC
- Film-music prompt and mastering practices: `bitwize-music-studio/claude-ai-music-skills`, CC0-1.0, https://github.com/bitwize-music-studio/claude-ai-music-skills
- Douyin safety-check inspiration: `CCCpan/chinese-sensitive-words-mcp`, MIT, https://github.com/CCCpan/chinese-sensitive-words-mcp
- Douyin planning inspiration: `yaojingang/yao-open-prompts`, MIT, https://github.com/yaojingang/yao-open-prompts
- Remotion production routing: `remotion-dev/skills`. This package links to the external Skill and does not vendor its rule set; the upstream repository did not expose a standard root license during this audit.
- Higgsfield explainer routing: `higgsfield-ai/skills`, MIT, https://github.com/higgsfield-ai/skills

## First-party specifications

- Seedance 2.5: ByteDance Seed official model page and launch article.
- Wan 3.0: official Wan creation site; the package labels its Wan prompt structure as a local production template because no fixed public prompt schema was found during this release audit.
- MiniMax H3: MiniMax official model repository and prompt-writing guides. The repository did not expose a recognized root license during this audit, so the package does not vendor the complete official Skill; it provides an original compatibility guide using required field names and links to the first-party source.

## Historical module ledger

The status of every historical top-level reference is recorded in `audits/component-ledger-v1-to-v2.1.md`. Local/original modules without a versioned upstream are integrity-checked but cannot be described as “latest.” On 2026-09-05, the publisher confirmed authority to release the seventeen previously unverified local snapshots under MIT. Do not represent third-party snapshots as original work or silently relicense them under the package's root license.

## Publication gate

The v2.1 publication gate is closed: the publisher confirmed the seventeen local snapshots, the two mixed-provenance internal files were replaced with original compatibility modules, and the repository now includes an MIT `LICENSE`. Third-party materials remain under their listed licenses. See `audits/publication-gate-v2.1.md` for the audit trail.
