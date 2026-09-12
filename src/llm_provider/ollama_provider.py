"""Free local LLM provider using existing Ollama binary + local model."""
import subprocess, json, re
from typing import List, Dict, Optional

class OllamaLLMProvider:
    """Provider using local ollama (free, no credentials, no external service)."""
    def __init__(self, model: str = "llama3.2:latest"):
        self.model = model

    def generate(self, question: str, evidence_snippets: List[str], context: Optional[Dict] = None) -> str:
        # Build a grounded prompt using ONLY the provided evidence
        evidence_text = "\n".join(f"- {s}" for s in evidence_snippets)
        prompt = f"""You are an evidence-first assistant. Answer ONLY using the evidence below. Do not invent facts. If evidence is insufficient for any claim, say so.

Question: {question}

Evidence:
{evidence_text}

Instructions:
- Answer in natural language.
- Each factual claim must be supported by the evidence above.
- If evidence does not fully support the answer, state the limitation clearly.
- Do not invent sources, numbers, dates, or names.

Answer:"""
        try:
            result = subprocess.run(
                ["ollama", "run", self.model, prompt],
                capture_output=True, text=True, timeout=180
            )
            output = result.stdout.strip()
            # Clean any leftover prompt artifacts
            output = re.sub(r"Instructions:.*?(Answer:)?", "", output, flags=re.S)
            output = output.replace("Answer:", "").strip()
            return output if output else "[No generated answer returned — evidence may be insufficient.]"
        except subprocess.TimeoutExpired:
            return "[LLM generation timed out — please try a shorter query or check model load.]"
        except Exception as e:
            return f"[LLM generation failed: {str(e)}. Answer could not be synthesized from evidence.]"
