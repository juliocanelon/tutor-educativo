from __future__ import annotations

import logging
import os
from typing import Dict

from flask import Flask, jsonify, render_template, request
from werkzeug.utils import secure_filename
from openai import OpenAI

from app.data.storage import (
    allowed_file,
    extract_text_from_pdf,
    get_book_metadata,
    load_book_text,
    store_book_metadata,
)
from app.orchestrator.core import Orchestrator
from app.quality.evaluator import ResponseEvaluator
from app.quality.optimizer import ResponseOptimizer
from app.workers.evaluator_gen import EvalWorker
from app.workers.tutor import TutorWorker
from app.workers.vocab import VocabWorker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Configuración de subida
app.config["UPLOAD_FOLDER"] = "uploads"
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB

if not os.path.exists(app.config["UPLOAD_FOLDER"]):
    os.makedirs(app.config["UPLOAD_FOLDER"])

_openai_client: OpenAI | None = None
_orchestrator: Orchestrator | None = None


def ensure_openai_client() -> OpenAI:
    """Crea el cliente de OpenAI usando la API key desde la variable de entorno."""
    global _openai_client
    if _openai_client is not None:
        return _openai_client

    if not os.environ.get("OPENAI_API_KEY"):
        raise EnvironmentError(
            "API key de OpenAI no configurada. Establece la variable de entorno OPENAI_API_KEY."
        )
    _openai_client = OpenAI()
    return _openai_client


def get_orchestrator() -> Orchestrator:
    global _orchestrator
    if _orchestrator is not None:
        return _orchestrator

    client = ensure_openai_client()
    workers: Dict[str, object] = {
        TutorWorker.name: TutorWorker(client),
        VocabWorker.name: VocabWorker(client),
        EvalWorker.name: EvalWorker(client),
    }
    evaluator = ResponseEvaluator(client)
    optimizer = ResponseOptimizer(client)
    _orchestrator = Orchestrator(workers=workers, evaluator=evaluator, optimizer=optimizer)
    return _orchestrator


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload_file():
    try:
        if "file" not in request.files:
            return jsonify({"error": "No se encontró el campo \"file\" en la solicitud."}), 400

        file = request.files["file"]

        if file.filename == "":
            return jsonify({"error": "No se seleccionó archivo."}), 400

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            file.save(filepath)

            store_book_metadata(filepath, filename)

            # Validamos que realmente podamos extraer algo
            _ = extract_text_from_pdf(filepath)

            return jsonify(
                {
                    "success": True,
                    "message": "Libro cargado exitosamente",
                    "title": filename,
                }
            ), 200

        return jsonify({"error": "Archivo no permitido. Solo PDFs."}), 400

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.json or {}
        user_message = data.get("message", "").strip()
        mode = data.get("mode", "explicar")
        age = data.get("age", 9)

        if not user_message:
            return jsonify({"error": "Mensaje vacío."}), 400

        book_content = load_book_text()
        metadata = get_book_metadata()

        orchestrator = get_orchestrator()
        result = orchestrator.handle(
            {
                "mode": mode,
                "message": user_message,
                "age": age,
                "book_text": book_content,
                "book_title": metadata.get("title"),
            }
        )

        response_payload = {
            "response": result.get("content"),
            "trace": result.get("trace"),
        }
        if result.get("anchor"):
            response_payload["anchor"] = result.get("anchor")
        return jsonify(response_payload), 200

    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 400
    except EnvironmentError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        logger.exception("Error en /chat")
        return jsonify({"error": f"Error en /chat: {str(e)}"}), 500


@app.route("/generate-questions", methods=["POST"])
def generate_questions():
    try:
        data = request.json or {}
        age = data.get("age", 9)

        book_content = load_book_text()
        metadata = get_book_metadata()

        orchestrator = get_orchestrator()
        result = orchestrator.handle(
            {
                "mode": "evaluar",
                "message": "Genera preguntas de comprensión lectora",
                "age": age,
                "book_text": book_content,
                "book_title": metadata.get("title"),
            }
        )

        return (
            jsonify(
                {
                    "questions": result.get("content"),
                    "trace": result.get("trace"),
                }
            ),
            200,
        )

    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 400
    except EnvironmentError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        logger.exception("Error en /generate-questions")
        return jsonify({"error": f"Error en /generate-questions: {str(e)}"}), 500


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
