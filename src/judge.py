"""RAGAS adapter: separate provider requests for n samples; no OpenAI n parameter."""
import asyncio
from langchain_core.outputs import Generation, LLMResult
from ragas.llms.base import BaseRagasLLM
from config import EVAL_MODEL, LLM_PROVIDER
from src.llm import completion, normalize_ragas_json


def _expects_json_list(prompt_text: str) -> bool:
    return ("sentence_index" in prompt_text or "attributed" in prompt_text or
            "series of statements" in prompt_text.lower())


class GeminiJudge(BaseRagasLLM):
    def __init__(self, model: str | None = None):
        super().__init__()
        self.model = model or EVAL_MODEL

    def generate_text(self, prompt, n=1, temperature=None, stop=None, callbacks=None):
        temperature = self.get_temperature(n) if temperature is None else temperature
        prompt_text = prompt.to_string()
        object_mode = not (LLM_PROVIDER == 'groq' and _expects_json_list(prompt_text))
        results = [Generation(text=normalize_ragas_json(completion(
            [{'role': 'user', 'content': prompt_text}], model=self.model,
            json_output=object_mode, temperature=temperature, cache_tag=f'ragas-sample-{i}'
        ))) for i in range(n)]
        return LLMResult(generations=[results])

    async def agenerate_text(self, prompt, n=1, temperature=None, stop=None, callbacks=None):
        return await asyncio.to_thread(self.generate_text, prompt, n, temperature, stop, callbacks)
