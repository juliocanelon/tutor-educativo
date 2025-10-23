"""Worker encargado de generar ilustraciones coherentes con el libro."""
from __future__ import annotations

from typing import Any, Dict, Optional

from openai import OpenAI


def _compose_visual_prompt(
    *,
    user_prompt: str,
    age: int,
    title: str,
    fragment: str,
) -> str:
    safe_fragment = fragment.strip()
    trimmed_fragment = safe_fragment[:900] if safe_fragment else ""

    guidance = (
        "Create a single illustrated scene for a children's book. The illustration must be "
        "delightful, warm and age-appropriate. Avoid any violent, frightening or mature "
        "content. Maintain consistency with the established characters of the book."
    )
    tone_clause = (
        "Target audience: children of {age} years old. Style: storybook illustration, clean lines, "
        "expressive characters, inclusive representation, bright but balanced colours."
    ).format(age=age)

    parts = [
        guidance,
        tone_clause,
        f"Book title: {title.strip() or 'Libro infantil'}.",
        f"User request: {user_prompt.strip()}.",
    ]
    if trimmed_fragment:
        parts.append(
            "Relevant excerpt from the book (use it for fidelity, not as text to display): "
            f"{trimmed_fragment}"
        )

    return "\n".join(parts)


class ImageWorker:
    name = "ImageWorker"

    def __init__(self, client: OpenAI):
        self.client = client

    def run(
        self,
        *,
        prompt: str,
        age: int,
        fragment: str,
        metadata: Dict[str, Any],
        context: Dict[str, str],
    ) -> Dict[str, Any]:
        title = metadata.get("title", "Libro")
        composed_prompt = _compose_visual_prompt(
            user_prompt=prompt,
            age=age,
            title=title,
            fragment=fragment or context.get("context", ""),
        )

        image_size = "1024x1024"
        response = self.client.images.generate(
            model="gpt-image-1",
            prompt=composed_prompt,
            size=image_size,
            quality="standard",
        )

        image_data = response.data[0]
        image_b64: Optional[str] = getattr(image_data, "b64_json", None)
        revised_prompt: Optional[str] = getattr(image_data, "revised_prompt", None)

        if not image_b64:
            raise RuntimeError("La generación de imagen no devolvió datos válidos.")

        try:
            width_str, height_str = image_size.split("x", maxsplit=1)
            width, height = int(width_str), int(height_str)
        except ValueError:  # pragma: no cover - defensive fallback
            width = height = 1024

        usage = {
            "model": getattr(response, "model", "gpt-image-1"),
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }

        payload: Dict[str, Any] = {
            "image_b64": image_b64,
            "mime_type": "image/png",
            "width": width,
            "height": height,
            "prompt_used": composed_prompt,
            "revised_prompt": revised_prompt,
            "usage": usage,
        }
        return payload
