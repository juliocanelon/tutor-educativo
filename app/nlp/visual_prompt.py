"""Generadores auxiliares para prompts visuales basados en libros."""
from __future__ import annotations

from typing import Any, Dict, Optional

from openai import OpenAI

from app.utils.usage import extract_usage

SYSTEM_PROMPT = (
    "Eres un especialista en diseñar prompts para ilustraciones infantiles. "
    "Tu objetivo es capturar la idea principal del libro y transformarla en una escena visual clara, "
    "segura y atractiva para el público de la edad indicada."
)


def generate_book_image_prompt(
    client: OpenAI,
    *,
    title: str,
    age: int,
    book_context: str,
    focus: str = "",
) -> Dict[str, Optional[Any]]:
    """Construye un prompt de ilustración inspirado en la idea central del libro."""
    context = (book_context or "").strip()
    if not context:
        raise ValueError("No hay contenido disponible para generar un prompt de imagen.")

    triple = '"""'
    cleaned_title = title.strip() or "Libro infantil"
    focus_clause = focus.strip()

    user_content_parts = [
        f"Título del libro: {cleaned_title}",
        f"Edad objetivo: {age} años",
        f"Idea principal del libro:\n{triple}{context[:1500]}{triple}",
        (
            f"Instrucción adicional del usuario: {focus_clause}"
            if focus_clause
            else "Sin instrucción adicional del usuario."
        ),
        (
            "Genera un único prompt en español para un generador de imágenes. "
            "Debe describir una escena ilustrada coherente con la idea principal, "
            "mencionar personajes clave, ambientación y estado de ánimo, e indicar un estilo "
            "apto para niñas y niños de la edad indicada."
        ),
        "No incluyas enumeraciones ni explicaciones. Usa como máximo tres frases."
        " Devuelve únicamente el prompt final listo para el generador de imágenes.",
    ]
    user_content = "\n\n".join(user_content_parts)

    completion = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        temperature=0.7,
        max_tokens=220,
    )

    prompt_text = completion.choices[0].message.content.strip()
    usage = extract_usage(completion)

    if not prompt_text:
        raise ValueError("La IA no devolvió un prompt de imagen válido.")

    return {"prompt": prompt_text, "usage": usage}
