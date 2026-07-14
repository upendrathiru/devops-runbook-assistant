"""
Pluggable LLM provider layer.

Swap providers via the RUNBOOK_LLM_PROVIDER env var — no other module needs
to change. This is what lets the same codebase run:
  - fully offline (MockLLMProvider) for demos/dev/CI,
  - against a real local LLaMA 2 checkpoint (HuggingFaceLLMProvider),
  - against a local Ollama server running llama2 (OllamaLLMProvider).
"""
from typing import List
from ingestion import Chunk
from config import LLM_PROVIDER, HF_MODEL_NAME, OLLAMA_URL, OLLAMA_MODEL, MAX_RESPONSE_TOKENS

SYSTEM_PROMPT = (
    "You are the DevOps Runbook Assistant. Answer operational questions ONLY "
    "using the provided runbook context. If the context does not contain the "
    "answer, say so plainly and suggest which runbook to check, rather than "
    "guessing. Always be concise and use numbered steps when the answer is a "
    "procedure."
)


def build_prompt(query: str, context_chunks: List[Chunk]) -> str:
    context_block = "\n\n".join(
        f"[Source: {c.source_title} — {c.section}]\n{c.text}"
        for c in context_chunks
    )
    return (
        f"{SYSTEM_PROMPT}\n\n"
        f"--- CONTEXT ---\n{context_block if context_block else '(no relevant context found)'}\n"
        f"--- END CONTEXT ---\n\n"
        f"Question: {query}\nAnswer:"
    )


class LLMProvider:
    def generate(self, query: str, context_chunks: List[Chunk]) -> str:
        raise NotImplementedError


class MockLLMProvider(LLMProvider):
    """
    Deterministic, fully offline responder. Produces a grounded, extractive
    answer built directly from the retrieved chunks, plus the same
    "I'm not sure" fallback behaviour the real model should follow.
    This lets the whole system (ingestion -> retrieval -> chat -> UI ->
    logging) be built, demoed, and tested without any GPU or model download.
    """

    def generate(self, query: str, context_chunks: List[Chunk]) -> str:
        if not context_chunks:
            return (
                "I'm not sure — I couldn't find anything relevant in the indexed "
                "runbooks for that question. Please check the runbook index "
                "directly or rephrase your question with more specific terms "
                "(e.g. a service name or procedure name)."
            )

        top = context_chunks[0]
        lines = [
            f"Based on **{top.source_title} → {top.section}**, here's what the runbook says:",
            "",
        ]
        # Extractive summary: pull the first few sentences of the top chunk,
        # formatted as steps if the text already looks like a numbered list.
        snippet = top.text.strip()
        import re as _re
        # If the chunk already contains "1. ... 2. ... 3. ..." style numbering,
        # split on the numbering itself so each step stays intact.
        numbered = _re.split(r"(?:(?<=\s)|^)(\d+)\.\s+", snippet)
        if len(numbered) > 2:
            # numbered alternates: [preamble, '1', step1, '2', step2, ...]
            preamble = numbered[0].strip()
            if preamble:
                lines.append(preamble)
            for i in range(1, len(numbered), 2):
                step_text = numbered[i + 1].strip() if i + 1 < len(numbered) else ""
                if step_text:
                    lines.append(f"{numbered[i]}. {step_text}")
        else:
            sentences = [s.strip() for s in snippet.replace("\n", " ").split(". ") if s.strip()]
            for s in sentences[:5]:
                bullet = s if s.endswith(".") else s + "."
                lines.append(f"- {bullet}")

        if len(context_chunks) > 1:
            lines.append("")
            lines.append("Related sections that may also help:")
            for c in context_chunks[1:]:
                lines.append(f"- {c.source_title} → {c.section}")

        lines.append("")
        lines.append(
            "_Note: this is a template-grounded response from the offline demo "
            "LLM provider. Configure RUNBOOK_LLM_PROVIDER=huggingface or "
            "RUNBOOK_LLM_PROVIDER=ollama for full generative answers._"
        )
        return "\n".join(lines)


class HuggingFaceLLMProvider(LLMProvider):
    """
    Loads a real causal LM (e.g. meta-llama/Llama-2-7b-chat-hf) via
    transformers. Requires: GPU with sufficient VRAM, `pip install
    transformers accelerate torch`, and a Hugging Face access token with
    LLaMA 2 license accepted (`huggingface-cli login`).
    """

    def __init__(self, model_name: str = HF_MODEL_NAME):
        from transformers import AutoTokenizer, AutoModelForCausalLM
        import torch
        self.torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name,
            torch_dtype=torch.float16,
            device_map="auto",
        )

    def generate(self, query: str, context_chunks: List[Chunk]) -> str:
        prompt = build_prompt(query, context_chunks)
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)
        outputs = self.model.generate(
            **inputs,
            max_new_tokens=MAX_RESPONSE_TOKENS,
            do_sample=False,
            temperature=0.2,
        )
        text = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        return text[len(prompt):].strip()


class OllamaLLMProvider(LLMProvider):
    """
    Calls a local Ollama server (https://ollama.com) running `llama2`.
    This is the fastest way to get a real LLaMA 2 model running without
    manually managing Hugging Face weights: `ollama pull llama2`.
    """

    def __init__(self, base_url: str = OLLAMA_URL, model: str = OLLAMA_MODEL):
        import requests
        self.requests = requests
        self.base_url = base_url.rstrip("/")
        self.model = model

    def generate(self, query: str, context_chunks: List[Chunk]) -> str:
        prompt = build_prompt(query, context_chunks)
        resp = self.requests.post(
            f"{self.base_url}/api/generate",
            json={"model": self.model, "prompt": prompt, "stream": False},
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json().get("response", "").strip()


_PROVIDER_SINGLETON: LLMProvider = None


def get_llm_provider() -> LLMProvider:
    global _PROVIDER_SINGLETON
    if _PROVIDER_SINGLETON is not None:
        return _PROVIDER_SINGLETON

    if LLM_PROVIDER == "huggingface":
        _PROVIDER_SINGLETON = HuggingFaceLLMProvider()
    elif LLM_PROVIDER == "ollama":
        _PROVIDER_SINGLETON = OllamaLLMProvider()
    else:
        _PROVIDER_SINGLETON = MockLLMProvider()
    return _PROVIDER_SINGLETON
