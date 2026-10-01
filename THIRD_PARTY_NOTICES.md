# Third-party notices

This package combines original routing instructions with attributed third-party Skill snapshots and adapted ideas. Inclusion does not change the original licenses.

## Exact or near-exact Skill snapshots

- `references/short-drama-writer.md` — `@ckchzh/short-drama-writer` v2.3.6, MIT-0, source: https://clawhub.ai/ckchzh/skills/short-drama-writer
- `references/story-cog.md` — `@cellcog/creative-writing-cellcog` v1.0.15, MIT-0, source: https://clawhub.ai/cellcog/skills/creative-writing-cellcog
- `references/cellcog.md` — `@cellcog/cellcog` v2.0.21, MIT-0, source: https://clawhub.ai/cellcog/skills/cellcog
- `references/video-generation-cellcog.md` — `@cellcog/video-generation-cellcog` v1.0.18, MIT-0, source: https://clawhub.ai/cellcog/skills/video-generation-cellcog
- Other bundled or adapted modules are enumerated in `manifests/dependencies.json` and retain their original authorship and terms. The repository MIT license does not override a listed third-party license.

## Adapted concepts

- Product/software promo shot vocabulary: `Vincentwei1021/video-shotcraft`, reviewed repository snapshot `5ddbf521038b0a7accfb6dc1e0a9eb29c67277ab`, Apache-2.0, Copyright 2026 Wei Yihao. The adapted module identifies modifications and fixed source cards. Full license: [video-shotcraft-Apache-2.0.md](references/support/licenses/video-shotcraft-Apache-2.0.md). No audio, template screenshots, Gallery media, or third-party brand footage is distributed here.
- Storyboard validation concepts: `eternityspring/shuohao-skills`, reviewed repository snapshot `ef4ac0c313c7eeb1f918db5f0f0eb319745900bc`, Apache-2.0, Copyright 2026 烁皓. The Python validator and local contract are original implementations, not copies of upstream runtime. [License](references/support/licenses/shuohao-Apache-2.0.md) and [NOTICE](references/support/licenses/shuohao-NOTICE.md) are preserved.
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
