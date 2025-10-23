"""Optimizer que reescribe prompts de imagen cuando el evaluador falla."""
from __future__ import annotations

import json
from typing import Any, Dict

from openai import OpenAI

from app.utils.usage import extract_usage

SYSTEM_PROMPT = (
    "Eres un especialista en adaptar prompts de ilustración infantil. "
    "Si el evaluador detectó problemas, reescribe el prompt manteniendo la intención original, "
    "haciendo énfasis en la seguridad y en la claridad para la edad indicada. "
    "Responde exclusivamente con un JSON válido."
)


class ImagePromptOptimizer:
    def __init__(self, client: OpenAI):
        self.client = client

    def optimise(
        self,
        *,
        prompt: str,
        age: int,
        metadata: Dict[str, Any],
        fragment: str,
        evaluation: Dict[str, Any],
    ) -> Dict[str, Any]:
        title = metadata.get("title", "Libro")
        failed = [name for name, ok in (evaluation.get("checks") or {}).items() if not ok]
        guidance = evaluation.get("feedback", "")
        triple = '"""'
        user_prompt = (
            f"Libro: {title}\n"
            f"Edad objetivo: {age} años\n"
            f"Fragmento de referencia:\n{triple}{fragment.strip()[:600]}{triple}\n\n"
            f"Prompt previo:\n{triple}{prompt.strip()}{triple}\n\n"
            f"Criterios a corregir: {', '.join(failed) if failed else 'ninguno explícito'}\n"
            f"Comentarios del evaluador: {guidance or 'sin comentarios'}\n\n"
            "Devuelve un JSON con el formato:\n"
            "{\n"
            "  \"prompt\": \"nuevo prompt más claro y seguro\",\n"
            "  \"notes\": \"breve explicación de los ajustes\"\n"
            "}"
        )

        completion = self.client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=220,
        )

        usage = extract_usage(completion)
        raw = completion.choices[0].message.content.strip()

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {"prompt": prompt, "notes": "No se pudo optimizar el prompt."}

        new_prompt = parsed.get("prompt", prompt).strip() or prompt
        notes = parsed.get("notes", "")

        return {
            "prompt": new_prompt,
            "notes": notes,
            "usage": usage,
            "raw": raw,
        }
