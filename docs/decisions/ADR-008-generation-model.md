# ADR-008: Generation Model

**Status:** Proposed

## Problem
Answer generation requires an LLM. The system should prefer local models ($0) but must ensure quality is acceptable for institutional use (faithfulness ≥ 97%, citation correctness ≥ 98%).

## Candidates Considered
1. **Local open-weight models** (Llama 3.3 70B, Qwen2.5 32B, etc.) — $0; privacy-preserving; variable quality
2. **Claude (Anthropic API)** — High quality; requires API costs; external
3. **GPT-4o (OpenAI API)** — High quality; requires API costs; external
4. **Hybrid: local for simple queries, API for complex** — Adaptive; more complex

## Experiment Plan
1. Run 50 benchmark cases through each model type
2. Measure: faithfulness (claim verified against evidence), citation correctness, completeness, abstention accuracy
3. Measure: latency, cost per query
4. Test on mixed Nepali/English content
5. Benchmark on LOCUS-specific terminology and formatting

## Decision Criteria
- Faithfulness ≥ 97% on development benchmark
- Citation correctness ≥ 98%
- Abstention accuracy ≥ 90%
- Local model acceptable if quality delta vs API < 3pp

## Architecture Note
The generation system uses an `LLMProvider` interface. Providers are configurable via model registry, not hardcoded.

```python
class LLMProvider(Protocol):
    def generate(self, prompt: str, evidence: EvidenceSet) -> str: ...
    def structured_output(self, prompt: str, schema: dict) -> dict: ...
```

## Revisit Conditions
- Re-evaluate if local model quality degrades on new content types
- Re-evaluate if API costs become prohibitive at scale
