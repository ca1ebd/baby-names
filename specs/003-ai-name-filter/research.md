# Research Notes: AI Name Filter

**Created**: 2026-08-08 (corpus sourcing split out to
[001-expanded-name-corpus/research.md](../001-expanded-name-corpus/research.md))
**Purpose**: Pre-planning research on best practices for AI-assisted filtering
of a large list.

## Best practices: filtering a big list with AI

The consistent pattern across industry and research writing is **hybrid
staging: deterministic rules first, model judgment second** — matching the
two-stage approach the owner proposed during clarification:

- Production classification systems typically use "rules for the easy cases,
  models for the long tail"; deterministic pre-filtering before LLM
  involvement is the primary cost lever, since LLM classification runs
  100–1000x the cost of a rule check
  ([Institute PM guide](https://www.institutepm.com/knowledge-hub/ai-classification-systems-guide),
  [Towards Data Science on hybrid deterministic + LLM systems](https://towardsdatascience.com/hybrid-ai-combining-deterministic-analytics-with-llm-reasoning/)).
- Two-step filtering — a cheap broad pass over the raw list, then a more
  careful pass over survivors — maintains accuracy while minimizing expensive
  calls ([LLM-Assisted Web Measurements](https://arxiv.org/pdf/2510.08101),
  [LLM-Based Filtering Stage overview](https://www.emergentmind.com/topics/llm-based-filtering-stage)).
- When the model must rank/select from many candidates, **listwise batching**
  (give the model a chunk of candidates and ask for the ones matching the
  brief) outperforms one-item-at-a-time pointwise calls on both quality and
  cost; multi-layer subgroup filtering scales this to large lists
  ([Multi-Layer Ranking with LLMs](https://arxiv.org/pdf/2406.11745),
  [RecRanker](https://arxiv.org/pdf/2312.16018)).

## Implications for this feature (to carry into /speckit-plan)

1. **Stage 0 — criteria translation (one AI call per criteria edit)**: turn
   the user's free text into (a) deterministic rules expressed in a fixed rule
   framework the app's filtering engine understands — a closed vocabulary of
   checks like starts-with, ends-with/sound patterns, length/syllables — and
   (b) a residual subjective brief ("feels classic, not trendy") for anything
   the framework can't express. The AI never filters names in this stage; it
   only emits rules for the engine to run. The framework's vocabulary is a
   plan-phase design decision (it bounds which criteria are "free and exact"
   vs. which need stage 2).
2. **Stage 1 — deterministic filter (free, on-device)**: apply those rules to
   the bundled corpus from spec 001. No network, no cost, zero violations by
   construction. For many criteria (like the owner's original no-D / no-"ey"
   rules) this stage alone fully answers the request.
3. **Stage 2 — subjective selection (metered AI, batched)**: only when a
   residual subjective brief exists, send stage-1 survivors in listwise
   batches for the model to keep/reject against the brief; cache verdicts per
   (criteria, name) so names are never re-judged for the same criteria —
   repeat batches get cheaper over time.

This ordering is what makes the Constitution II cost posture credible: the
default experience (no criteria) costs nothing, criteria that translate
entirely into rules cost a single translation call, and only genuinely
subjective criteria consume the metered, rate-capped service.

## Sources

- [Institute PM: Classification Systems — When to Use Rules, ML, or LLMs](https://www.institutepm.com/knowledge-hub/ai-classification-systems-guide)
- [Towards Data Science: Hybrid AI — Combining Deterministic Analytics with LLM Reasoning](https://towardsdatascience.com/hybrid-ai-combining-deterministic-analytics-with-llm-reasoning/)
- [LLM-Assisted Web Measurements (two-step filtering)](https://arxiv.org/pdf/2510.08101)
- [Multi-Layer Ranking with Large Language Models](https://arxiv.org/pdf/2406.11745)
- [RecRanker: LLMs as rankers](https://arxiv.org/pdf/2312.16018)
- [Emergent Mind: LLM-Based Filtering Stage](https://www.emergentmind.com/topics/llm-based-filtering-stage)
