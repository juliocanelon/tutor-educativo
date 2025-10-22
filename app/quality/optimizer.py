from __future__ import annotations

from typing import Any, Dict

from openai import OpenAI

from app.utils.usage import extract_usage

OPTIMIZER_PROMPT = (
    "Eres un tutor experimentado que mejora respuestas educativas según la retroalimentación del evaluador. "
    "Respeta siempre el contexto del libro y la edad del estudiante."
)


class ResponseOptimizer:
    def __init__(self, client: OpenAI):
        self.client = client

    def optimise(
        self,
        *,
        worker_name: str,
        previous_answer: str,
        evaluation: Dict[str, Any],
        context: Dict[str, Any],
        age: int,
        message: str,
        metadata: Dict[str, Any],
    ) -> str:
        failed_checks = [name for name, passed in evaluation.get("checks", {}).items() if not passed]
        guidance = evaluation.get("feedback", "")

        system_prompt = (
            f"{OPTIMIZER_PROMPT} Estás corrigiendo la salida de {worker_name}. "
            "Debes asegurar que los criterios fallidos se cumplan y conservar la"
            " adecuación al nivel de edad indicado."
        )

        fragment = context.get("context", "")
        title = metadata.get("title", "Libro")
        triple = '"""'
        user_prompt = (
            f"Libro: {title}\n"
            f"Edad del estudiante: {age} años\n"
            f"Fragmento disponible:\n{triple}{fragment}{triple}\n\n"
            f"Pregunta original: {message}\n"
            f"Respuesta previa:\n{triple}{previous_answer}{triple}\n\n"
            f"Criterios fallidos: {', '.join(failed_checks) or 'Ninguno'}\n"
            f"Guía del evaluador: {guidance}\n\n"
            f"Genera una nueva respuesta completa cumpliendo los formatos solicitados para {worker_name}."
        )

        completion = self.client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.4,
            max_tokens=400,
        )

        usage = extract_usage(completion)
        answer = completion.choices[0].message.content.strip()
        return {"content": answer, "usage": usage}
