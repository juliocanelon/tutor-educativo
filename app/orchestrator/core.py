"""Core orchestrator coordinating workers and quality loop."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.nlp.rag import build_context
from app.quality.evaluator import ResponseEvaluator
from app.quality.optimizer import ResponseOptimizer
from app.quality.image_prompt_evaluator import ImagePromptEvaluator
from app.quality.image_prompt_optimizer import ImagePromptOptimizer

LOGGER = logging.getLogger(__name__)


class Orchestrator:
    def __init__(
        self,
        *,
        workers: Dict[str, Any],
        evaluator: ResponseEvaluator,
        optimizer: ResponseOptimizer,
        image_prompt_evaluator: Optional[ImagePromptEvaluator] = None,
        image_prompt_optimizer: Optional[ImagePromptOptimizer] = None,
        max_retries: int = 2,
    ) -> None:
        self.workers = workers
        self.evaluator = evaluator
        self.optimizer = optimizer
        self.image_prompt_evaluator = image_prompt_evaluator
        self.image_prompt_optimizer = image_prompt_optimizer
        self.max_retries = max_retries

    @staticmethod
    def _resolve_worker_name(mode: str | None) -> str:
        mapping = {
            "explicar": "TutorWorker",
            "vocabulario": "VocabWorker",
            "evaluar": "EvalWorker",
            "imagen": "ImageWorker",
        }
        if not mode:
            return "TutorWorker"
        return mapping.get(mode.lower(), "TutorWorker")

    def handle(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        mode = payload.get("mode")
        worker_name = self._resolve_worker_name(mode)
        worker = self.workers.get(worker_name)
        if not worker:
            raise ValueError(f"Worker no configurado para modo {mode}")

        if worker_name == "ImageWorker":
            return self._handle_image(worker, payload)

        message = payload.get("message", "")
        age = int(payload.get("age", 9))
        book_text = payload.get("book_text", "")
        metadata = {
            "title": payload.get("book_title", "Libro"),
        }

        context = build_context(book_text, message if message else metadata.get("title"))
        LOGGER.info("Orchestrator routing to %s", worker_name)

        attempt = worker.run(message=message, age=age, context=context, metadata=metadata)
        candidate = attempt.get("content", "")
        usage_events: List[Dict[str, Any]] = []

        if attempt.get("usage"):
            usage_events.append(
                {
                    **attempt["usage"],
                    "stage": worker_name,
                    "retry": 0,
                }
            )

        evaluation = self.evaluator.evaluate(
            worker_name=worker_name,
            candidate=candidate,
            context=context,
        )

        if evaluation.get("usage"):
            usage_events.append(
                {
                    **evaluation["usage"],
                    "stage": "evaluation",
                    "retry": 0,
                }
            )

        retries = 0
        while not evaluation.get("passed", False) and retries < self.max_retries:
            LOGGER.info("Optimizer triggered for %s (retry %s)", worker_name, retries + 1)
            optimisation = self.optimizer.optimise(
                worker_name=worker_name,
                previous_answer=candidate,
                evaluation=evaluation,
                context=context,
                age=age,
                message=message,
                metadata=metadata,
            )
            if isinstance(optimisation, dict):
                candidate = optimisation.get("content", "")
                optimisation_usage = optimisation.get("usage")
            else:  # pragma: no cover - backward compatibility
                candidate = optimisation
                optimisation_usage = None

            if optimisation_usage:
                usage_events.append(
                    {
                        **optimisation_usage,
                        "stage": "optimizer",
                        "retry": retries + 1,
                    }
                )
            evaluation = self.evaluator.evaluate(
                worker_name=worker_name,
                candidate=candidate,
                context=context,
            )
            if evaluation.get("usage"):
                usage_events.append(
                    {
                        **evaluation["usage"],
                        "stage": "evaluation",
                        "retry": retries + 1,
                    }
                )
            retries += 1

        trace = {
            "worker": worker_name,
            "checks": evaluation.get("checks", {}),
            "retries": retries,
            "feedback": evaluation.get("feedback", ""),
        }

        return {
            "content": candidate,
            "trace": trace,
            "anchor": attempt.get("anchor", ""),
            "usage": usage_events,
        }

    def _handle_image(self, worker: Any, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self.image_prompt_evaluator or not self.image_prompt_optimizer:
            raise RuntimeError("El evaluador/optimizador de prompts de imagen no está configurado.")

        raw_prompt = (payload.get("prompt") or payload.get("message") or "").strip()
        if not raw_prompt:
            raise ValueError("El prompt de imagen está vacío.")

        age = int(payload.get("age", 9))
        book_text = payload.get("book_text", "")
        provided_fragment = (payload.get("fragment") or "").strip()
        metadata = {
            "title": payload.get("book_title", "Libro"),
        }

        context = build_context(book_text, raw_prompt or metadata.get("title"))
        contextual_fragment = context.get("context", "").strip()

        fragments: List[str] = []
        if provided_fragment:
            fragments.append(provided_fragment)
        if contextual_fragment and contextual_fragment not in provided_fragment:
            fragments.append(contextual_fragment)
        combined_fragment = "\n\n".join(fragments)[:1200]

        usage_events: List[Dict[str, Any]] = []
        retries = 0
        candidate_prompt = raw_prompt
        last_evaluation: Dict[str, Any] = {}
        optimizer_notes: List[str] = []

        while True:
            evaluation = self.image_prompt_evaluator.evaluate(
                prompt=candidate_prompt,
                age=age,
                metadata=metadata,
                fragment=combined_fragment or contextual_fragment,
            )
            last_evaluation = evaluation

            if evaluation.get("usage"):
                usage_events.append(
                    {
                        **evaluation["usage"],
                        "stage": "image_prompt_evaluator",
                        "retry": retries,
                    }
                )

            if evaluation.get("passed", False) or retries >= self.max_retries:
                break

            optimisation = self.image_prompt_optimizer.optimise(
                prompt=candidate_prompt,
                age=age,
                metadata=metadata,
                fragment=combined_fragment or contextual_fragment,
                evaluation=evaluation,
            )
            candidate_prompt = optimisation.get("prompt", candidate_prompt)
            notes = optimisation.get("notes")
            if notes:
                optimizer_notes.append(str(notes))

            optimisation_usage = optimisation.get("usage")
            if optimisation_usage:
                usage_events.append(
                    {
                        **optimisation_usage,
                        "stage": "image_prompt_optimizer",
                        "retry": retries + 1,
                    }
                )

            retries += 1

        worker_result = worker.run(
            prompt=candidate_prompt,
            age=age,
            fragment=combined_fragment or contextual_fragment,
            metadata=metadata,
            context=context,
        )

        worker_usage = worker_result.get("usage")
        if worker_usage:
            usage_events.append(
                {
                    **worker_usage,
                    "stage": "image_worker",
                    "retry": retries,
                }
            )

        feedback_notes = [last_evaluation.get("feedback", "").strip()]
        feedback_notes.extend(optimizer_notes)
        feedback = " | ".join(note for note in feedback_notes if note)

        trace = {
            "worker": "ImageWorker",
            "checks": last_evaluation.get("checks", {}),
            "retries": retries,
            "feedback": feedback,
        }

        payload_out = {
            "image": {
                "data": worker_result.get("image_b64"),
                "mime_type": worker_result.get("mime_type", "image/png"),
                "width": worker_result.get("width"),
                "height": worker_result.get("height"),
            },
            "prompt": candidate_prompt,
            "revised_prompt": worker_result.get("revised_prompt"),
            "trace": trace,
            "fragment": combined_fragment or contextual_fragment,
            "usage": usage_events,
        }

        return payload_out
