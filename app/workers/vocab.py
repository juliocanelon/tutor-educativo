from __future__ import annotations

from typing import Any, Dict

from openai import OpenAI

from app.utils.usage import extract_usage


VOCAB_PROMPT = (
    "Eres un mentor lingüístico para niños. Identifica y explica vocabulario difícil "
    "del fragmento suministrado. Usa ejemplos sencillos y cercanos a la vida del niño y "
    "adapta la complejidad a la edad proporcionada."
)


class VocabWorker:
    name = "VocabWorker"

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
        if age <= 8:
            age_guidance = (
                "Usa definiciones muy concretas, palabras del día a día y actividades"
                " lúdicas de pocos pasos."
            )
        elif age <= 12:
            age_guidance = (
                "Explica con lenguaje escolar, incluye sinónimos sencillos y propone"
                " ejemplos que inviten a relacionar con su entorno."
            )
        else:
            age_guidance = (
                "Puedes ampliar con matices y contrastes, conecta con intereses de"
                " secundaria y fomenta reflexión breve."
            )

        system_prompt = (
            f"{VOCAB_PROMPT} El lector tiene {age} años. {age_guidance} "
            "Incluye siempre un ejemplo contextual y una mini actividad breve."
        )

        fragment = context.get("context", "")
        title = metadata.get("title", "Libro")
        triple = '"""'
        user_prompt = (
            f"Libro: {title}\n"
            f"Fragmento para analizar:\n{triple}{fragment}{triple}\n\n"
            f"Solicitud del estudiante: {message or 'Explica el vocabulario difícil'}\n\n"
            "Devuelve una lista numerada con el formato:\n"
            "- Palabra: definición amigable.\n"
            "- Ejemplo contextual tomado o inspirado en el fragmento.\n"
            "- Mini actividad de uso."
        )

        completion = self.client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.5,
            max_tokens=360,
        )

        answer = completion.choices[0].message.content.strip()
        usage = extract_usage(completion)
        return {
            "content": answer,
            "anchor": context.get("anchor", ""),
            "usage": usage,
        }
