from __future__ import annotations

from typing import Any, Dict

from openai import OpenAI

from app.utils.usage import extract_usage

TUTOR_PROMPT = (
    "Eres un tutor pedagógico experto en comprensión lectora infantil. "
    "Utiliza el fragmento del libro para responder de manera clara y motivadora. "
    "Debes: 1) explicar la respuesta con lenguaje amigable, 2) mencionar explícitamente "
    "la cita textual de apoyo, 3) cerrar con una mini-pregunta para invitar a la reflexión. "
    "Adapta ejemplos, vocabulario y extensión de acuerdo con la edad recibida."
)


class TutorWorker:
    name = "TutorWorker"

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
        """Generate a response anchored to the provided context."""
        if age <= 8:
            age_guidance = (
                "Usa frases cortas (máx. 12 palabras), vocabulario concreto y compara con"
                " experiencias cotidianas de la infancia temprana."
            )
        elif age <= 12:
            age_guidance = (
                "Mantén un tono cercano, explica vocabulario nuevo en contexto y combina"
                " oraciones simples con alguna pregunta guiada."
            )
        else:
            age_guidance = (
                "Profundiza en ideas clave con cohesión, emplea ejemplos que conecten con"
                " la adolescencia temprana y evita tecnicismos innecesarios."
            )

        system_prompt = (
            f"{TUTOR_PROMPT} El lector tiene {age} años. "
            f"{age_guidance} Ajusta la complejidad, longitud y tono para esa edad y evita"
            " información fuera del fragmento."
        )

        fragment = context.get("context", "")
        title = metadata.get("title", "Libro")
        triple = '"""'
        user_content = (
            f"Libro: {title}\n"
            f"Fragmento relevante:\n{triple}{fragment}{triple}\n\n"
            f"Pregunta del estudiante: {message}\n\n"
            "Responde siguiendo este formato claro:\n"
            "1. Explicación principal (2-3 frases).\n"
            "2. Referencia textual: cita exacta entre comillas del fragmento entregado.\n"
            "3. Mini-pregunta motivadora."
        )

        completion = self.client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            temperature=0.6,
            max_tokens=380,
        )

        answer = completion.choices[0].message.content.strip()
        usage = extract_usage(completion)
        return {
            "content": answer,
            "anchor": context.get("anchor", ""),
            "usage": usage,
        }
