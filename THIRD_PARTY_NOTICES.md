# Third-party notices

This package combines original routing instructions with attributed third-party Skill snapshots and adapted ideas. Inclusion does not change the original licenses.

## Exact or near-exact Skill snapshots

- `references/short-drama-writer.md` — `@ckchzh/short-drama-writer` v2.3.6, MIT-0, source: https://clawhub.ai/ckchzh/skills/short-drama-writer
- `references/story-cog.md` — `@cellcog/creative-writing-cellcog` v1.0.15, MIT-0, source: https://clawhub.ai/cellcog/skills/creative-writing-cellcog
- `references/cellcog.md` — `@cellcog/cellcog` v2.0.21, MIT-0, source: https://clawhub.ai/cellcog/skills/cellcog
- `references/video-generation-cellcog.md` — `@cellcog/video-generation-cellcog` v1.0.18, MIT-0, source: https://clawhub.ai/cellcog/skills/video-generation-cellcog
- Other bundled or adapted modules are enumerated in `manifests/dependencies.json` and retain their original authorship and terms. The repository MIT license does not override a listed third-party license.

## Adapted concepts

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
