from __future__ import annotations

import json
from typing import Any, Dict

from openai import OpenAI


CHECKLISTS = {
    "TutorWorker": ["anchored", "clarity", "structure", "safety"],
    "VocabWorker": ["anchored", "clarity", "structure", "safety"],
    "EvalWorker": ["variety", "distractores", "feedback", "difficulty"],
}

EVALUATOR_PROMPT = (
    "Eres un evaluador pedagógico. Revisa la respuesta producida por el agente y la lista de "
    "chequeo correspondiente. Evalúa cada criterio con true/false y ofrece comentarios."
)


class ResponseEvaluator:
    def __init__(self, client: OpenAI):
        self.client = client

    def evaluate(
        self,
        *,
        worker_name: str,
        candidate: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        checklist = CHECKLISTS.get(worker_name, [])
        checklist_str = ", ".join(checklist)

        system_prompt = (
            f"{EVALUATOR_PROMPT} Si no puedes validar un criterio, márcalo como false."
        )

        fragment = context.get("context", "")
        triple = '"""'
        checklist_entries = ", ".join(f'"{item}": true/false' for item in checklist)
        user_prompt = (
            f"Worker: {worker_name}\n"
            f"Checklist: {checklist_str}\n"
            f"Contexto disponible:\n{triple}{fragment}{triple}\n"
            f"Respuesta producida:\n{triple}{candidate}{triple}\n\n"
            "Devuelve un JSON válido con la forma:\n"
            "{\n"
            f"  \"checks\": {{{checklist_entries}}},\n"
            "  \"feedback\": \"Observaciones breves\"\n"
            "}"
        )

        completion = self.client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.0,
            max_tokens=260,
        )

        raw = completion.choices[0].message.content.strip()
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {"checks": {item: False for item in checklist}, "feedback": "Formato inválido"}

        checks = parsed.get("checks", {})
        normalised_checks = {item: bool(checks.get(item, False)) for item in checklist}
        passed = all(normalised_checks.values()) if checklist else True

        return {
            "checks": normalised_checks,
            "feedback": parsed.get("feedback", ""),
            "passed": passed,
            "raw": raw,
        }
