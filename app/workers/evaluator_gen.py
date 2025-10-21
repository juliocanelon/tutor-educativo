from __future__ import annotations

from typing import Any, Dict

from openai import OpenAI


EVAL_GENERATOR_PROMPT = (
    "Eres un diseñador de evaluaciones lectoras para niños. "
    "Debes elaborar bloques de preguntas literal, inferencial y crítica con retroalimentación."
)


class EvalWorker:
    name = "EvalWorker"

    def __init__(self, client: OpenAI):
        self.client = client

    def run(
        self,
        *,
        message: str,
        age: int,
        context: Dict[str, str],
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        system_prompt = (
            f"{EVAL_GENERATOR_PROMPT} El material corresponde a estudiantes de {age} años. "
            "Incluye variación en formatos (opción múltiple, respuesta corta) y retroalimentación."
        )

        fragment = context.get("context", "")
        title = metadata.get("title", "Libro")
        triple = '"""'
        user_prompt = (
            f"Libro: {title}\n"
            f"Fragmento de referencia:\n{triple}{fragment}{triple}\n\n"
            "Genera preguntas de comprensión siguiendo este formato:\n"
            "### Literal\n"
            "1. Pregunta...\n"
            "   - Tipo de respuesta y distractores si aplica.\n"
            "   - Retroalimentación o pista.\n"
            "### Inferencial\n"
            "...\n"
            "### Crítica\n"
            "...\n"
            "Incluye un cierre con sugerencias para el docente."
        )

        completion = self.client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            max_tokens=500,
        )

        answer = completion.choices[0].message.content.strip()
        return {"content": answer, "anchor": context.get("anchor", "")}
