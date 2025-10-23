"""Core orchestrator coordinating workers and quality loop."""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from app.nlp.rag import build_context
from app.quality.evaluator import ResponseEvaluator
from app.quality.optimizer import ResponseOptimizer

LOGGER = logging.getLogger(__name__)


class Orchestrator:
    def __init__(
        self,
        *,
        workers: Dict[str, Any],
        evaluator: ResponseEvaluator,
        optimizer: ResponseOptimizer,
        max_retries: int = 2,
    ) -> None:
        self.workers = workers
        self.evaluator = evaluator
        self.optimizer = optimizer
        self.max_retries = max_retries

    @staticmethod
    def _resolve_worker_name(mode: str | None) -> str:
        mapping = {
            "explicar": "TutorWorker",
            "vocabulario": "VocabWorker",
            "evaluar": "EvalWorker",
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
