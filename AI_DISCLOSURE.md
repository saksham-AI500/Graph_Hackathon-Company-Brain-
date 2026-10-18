# AI Assistance & Tools Disclosure

In accordance with the official Graph Hacks 2026 hackathon guidelines, this document discloses all AI tools, models, and assistants utilized during the research, design, development, and evaluation of **RepoBrain** (Track 03 — Company Brain).

---

## 1. AI Tools and Roles

| Tool / Model | Primary Role | Description of Use |
| :--- | :--- | :--- |
| **Google Antigravity IDE** (Gemini 2.5 Pro architecture) | **Pair Programming & Autonomous Coding Agent** | Assisted with codebase implementation, FastAPI routes, FalkorDB Cypher query authoring, refactoring, test suite development (319 tests), and automated verification harness execution. |
| **Google Stitch** | **UI / UX Design & Screen Prototyping** | Generated the initial design system, dark-mode color tokens, typography tokens, layout specifications, and exported screens (`/ask`, `/compare`, `/graph`, `/evaluation`). |
| **Claude (Anthropic)** | **Domain Research & Evaluation Methodology** | Assisted in researching graph-grounded provenance mechanisms, NLI verifier boundary designs, adversarial test case generation, and leakage audit checklists. |
| **LiquidAI LFM-2.5-2.6B** (`liquid/lfm-2.5-2.6b:free`) | **Product LLM Route (Inference)** | Active model route configured via OpenRouter for multi-turn tool calling and answer synthesis during `graph_on` and `graph_off` queries. |
| **Cross-Encoder MiniLM2** (`cross-encoder/nli-MiniLM2-L6-H768`) | **Local NLI Verification Model** | Local ONNX cross-encoder model used for deterministic, offline natural language inference (NLI) sentence-to-source entailment scoring. |

---

## 2. Human Review & Oversight

- **All code, architecture, schema designs, and test suites were reviewed and validated by humans.**
- Ground truth rubrics, evaluation data assertions, and acceptance criteria were validated against authentic repository records and frozen prior to scoring.
- Synthetic fixtures were verified for integrity, timestamps, and schema alignment.
- Zero unverifiable claims or synthetic metrics were added without human audit and machine execution logs.
