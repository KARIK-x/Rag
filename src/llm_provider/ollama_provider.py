"""Free local LLM provider using existing Ollama binary + local model."""
import subprocess, json, re
from typing import List, Dict, Optional

class OllamaLLMProvider:
    """Provider using local ollama (free, no credentials, no external service)."""
    def __init__(self, model: str = "llama3.2:latest"):
        self.model = model

    def generate(self, question: str, evidence_snippets: List[str], context: Optional[Dict] = None) -> str:
        # Build a grounded prompt using ONLY the provided evidence
        # If evidence snippets contain real document context (heading + text), synthesize naturally
        evidence_text = "\n".join(f"- [{i+1}] {s}" for i, s in enumerate(evidence_snippets))
        prompt = f"""You are an evidence-first assistant. Answer ONLY using the evidence below. Do not invent facts.

Question: {question}

Evidence:
{evidence_text}

Instructions:
- If the evidence clearly contains the answer, provide a concise natural-language answer summarizing the key point with the source document mentioned.
- If evidence is partial, say what can be established and what is missing.
- If evidence does not support a specific claim, state the limitation clearly.
- Each factual claim must cite its source document where available.
- Do not invent sources, years, names, or roles not in the evidence.

Answer:"""
        try:
            # Verify ollama actually invoked and returns real output
            result = subprocess.run(
                ["ollama", "run", self.model, prompt],
                capture_output=True, text=True, timeout=180
            )
            output = result.stdout.strip()
            # If empty but stderr present, include diagnostic (truthful, no fabrication)
            if not output and result.stderr:
                return f"[LLM generation returned empty stdout; stderr: {result.stderr[:300]}]"
            # Clean any leftover prompt artifacts
            output = re.sub(r"Instructions:.*?(Answer:)?", "", output, flags=re.S)
            output = output.replace("Answer:", "").strip()
            return output if output else "[No generated answer returned — evidence may be insufficient.]"
        except subprocess.TimeoutExpired:
            return "[LLM generation timed out — please try a shorter query or check model load.]"
        except Exception as e:
            return f"[LLM generation failed: {str(e)}. Answer could not be synthesized from evidence.]"
