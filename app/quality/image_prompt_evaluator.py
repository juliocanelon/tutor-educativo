"""Evaluator que valida prompts antes de generar ilustraciones."""
from __future__ import annotations

import json
from typing import Any, Dict

from openai import OpenAI

from app.utils.usage import extract_usage

IMAGE_CHECKLIST = ["clarity", "safety", "coherence"]

SYSTEM_PROMPT = (
    "Eres un evaluador especializado en prompts para ilustraciones infantiles. "
    "Debes comprobar que el texto sea claro, seguro para la edad indicada y coherente con el libro." 
    "Responde siempre en JSON válido."
)


class ImagePromptEvaluator:
    def __init__(self, client: OpenAI):
        self.client = client

    def evaluate(
        self,
        *,
        prompt: str,
        age: int,
        metadata: Dict[str, Any],
        fragment: str,
    ) -> Dict[str, Any]:
        title = metadata.get("title", "Libro")
        triple = '"""'
        user_prompt = (
            f"Libro: {title}\n"
            f"Edad objetivo: {age} años\n"
            f"Fragmento de referencia:\n{triple}{fragment.strip()[:600]}{triple}\n\n"
            f"Prompt propuesto:\n{triple}{prompt.strip()}{triple}\n\n"
            "Valida los criterios claridad, safety y coherence. Si alguna dimensión es dudosa o incompleta, márcala como false.\n"
            "Devuelve un JSON con la forma:\n"
            "{\n"
            "  \"checks\": {\"clarity\": true/false, \"safety\": true/false, \"coherence\": true/false},\n"
            "  \"feedback\": \"Observaciones breves\"\n"
            "}"
        )

        completion = self.client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.0,
            max_tokens=200,
        )

        usage = extract_usage(completion)
        raw = completion.choices[0].message.content.strip()

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {
                "checks": {item: False for item in IMAGE_CHECKLIST},
                "feedback": "No se pudo interpretar la validación.",
            }

        checks = parsed.get("checks", {})
        normalised_checks = {item: bool(checks.get(item, False)) for item in IMAGE_CHECKLIST}
        passed = all(normalised_checks.values())

        return {
            "checks": normalised_checks,
            "feedback": parsed.get("feedback", ""),
            "passed": passed,
            "raw": raw,
            "usage": usage,
        }
