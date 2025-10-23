from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Dict, List
from uuid import uuid4

from flask import Flask, jsonify, render_template, request, session
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
from app.nlp.rag import build_context
from app.quality.evaluator import ResponseEvaluator
from app.quality.optimizer import ResponseOptimizer
from app.quality.image_prompt_evaluator import ImagePromptEvaluator
from app.quality.image_prompt_optimizer import ImagePromptOptimizer
from app.workers.evaluator_gen import EvalWorker
from app.workers.tutor import TutorWorker
from app.workers.vocab import VocabWorker
from app.workers.image import ImageWorker

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


def uploads_directory() -> str:
    return os.path.abspath(app.config["UPLOAD_FOLDER"])


def is_safe_upload_path(path: str) -> bool:
    """Verifica que el path apunte dentro del directorio de uploads."""
    uploads_dir = uploads_directory()
    normalized = os.path.normpath(path or "")

    if os.path.isabs(normalized):
        candidate = os.path.abspath(normalized)
    else:
        # Permite que venga con prefijo "uploads/" o relativo
        if normalized.startswith(app.config["UPLOAD_FOLDER"]):
            relative = os.path.relpath(normalized, app.config["UPLOAD_FOLDER"])
        else:
            relative = normalized
        candidate = os.path.abspath(os.path.join(uploads_dir, relative))

    return candidate.startswith(uploads_dir + os.sep) or candidate == uploads_dir


def resolve_upload_path(path: str) -> str:
    """Normaliza un path validado y devuelve la ruta absoluta."""
    if not path:
        raise ValueError("Ruta de archivo no proporcionada.")

    if not is_safe_upload_path(path):
        raise ValueError("Ruta de archivo inválida.")

    uploads_dir = uploads_directory()
    normalized = os.path.normpath(path)
    if os.path.isabs(normalized):
        resolved = os.path.abspath(normalized)
    else:
        if normalized.startswith(app.config["UPLOAD_FOLDER"]):
            relative = os.path.relpath(normalized, app.config["UPLOAD_FOLDER"])
        else:
            relative = normalized
        resolved = os.path.abspath(os.path.join(uploads_dir, relative))

    if not resolved.startswith(uploads_dir + os.sep):
        raise ValueError("Ruta de archivo inválida.")

    return resolved


def list_books() -> List[Dict[str, object]]:
    """Devuelve la lista de PDFs disponibles ordenados por fecha de modificación."""
    uploads_dir = uploads_directory()
    items: List[Dict[str, object]] = []
    if not os.path.exists(uploads_dir):
        return items

    current_book_path = session.get("book_path")

    for entry in os.scandir(uploads_dir):
        if not entry.is_file():
            continue
        if not entry.name.lower().endswith(".pdf"):
            continue
        stats = entry.stat()
        relative_path = os.path.join(app.config["UPLOAD_FOLDER"], entry.name)
        items.append(
            {
                "name": entry.name,
                "path": relative_path,
                "size": stats.st_size,
                "mtime": int(stats.st_mtime),
                "selected": os.path.abspath(entry.path) == (current_book_path or ""),
            }
        )

    items.sort(key=lambda item: item["mtime"], reverse=True)
    return items


def ensure_unique_filename(directory: str, filename: str) -> str:
    """Genera un nombre único en caso de colisión."""
    candidate = filename
    base, ext = os.path.splitext(filename)
    while os.path.exists(os.path.join(directory, candidate)):
        timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        candidate = f"{base}_{timestamp}_{uuid4().hex[:4]}{ext}"
    return candidate


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
        ImageWorker.name: ImageWorker(client),
    }
    evaluator = ResponseEvaluator(client)
    optimizer = ResponseOptimizer(client)
    image_prompt_evaluator = ImagePromptEvaluator(client)
    image_prompt_optimizer = ImagePromptOptimizer(client)
    _orchestrator = Orchestrator(
        workers=workers,
        evaluator=evaluator,
        optimizer=optimizer,
        image_prompt_evaluator=image_prompt_evaluator,
        image_prompt_optimizer=image_prompt_optimizer,
    )
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
            uploads_dir = uploads_directory()
            filename = ensure_unique_filename(uploads_dir, filename)
            filepath = os.path.join(uploads_dir, filename)
            file.save(filepath)

            store_book_metadata(filepath, filename)

            # Validamos que realmente podamos extraer algo
            _ = extract_text_from_pdf(filepath)

            return jsonify(
                {
                    "success": True,
                    "message": "Libro cargado exitosamente",
                    "title": filename,
                    "path": os.path.join(app.config["UPLOAD_FOLDER"], filename),
                }
            ), 200

        return jsonify({"error": "Archivo no permitido. Solo PDFs."}), 400

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/books", methods=["GET"])
def get_books():
    try:
        items = list_books()
        return jsonify({"items": items}), 200
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Error al listar libros")
        return jsonify({"error": f"No se pudieron listar los libros: {exc}"}), 500


@app.route("/book-fragment", methods=["POST"])
def book_fragment():
    try:
        data = request.json or {}
        focus = (data.get("focus") or "").strip()

        book_content = load_book_text()
        metadata = get_book_metadata()

        context = build_context(book_content, focus or metadata.get("title"))
        fragment = (context.get("context") or "")[:480].strip()

        if not fragment:
            return jsonify({"error": "No se pudo obtener un fragmento del libro."}), 400

        return jsonify({"fragment": fragment}), 200

    except FileNotFoundError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Error al obtener fragmento del libro")
        return jsonify({"error": f"No se pudo obtener el fragmento: {exc}"}), 500


@app.route("/use-book", methods=["POST"])
def use_book():
    data = request.json or {}
    path = data.get("path")
    try:
        resolved_path = resolve_upload_path(path)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    if not os.path.exists(resolved_path) or not os.path.isfile(resolved_path):
        return jsonify({"error": "El archivo especificado no existe."}), 404

    title = os.path.basename(resolved_path)
    store_book_metadata(resolved_path, title)
    relative_path = os.path.join(app.config["UPLOAD_FOLDER"], title)
    return (
        jsonify(
            {
                "success": True,
                "title": title,
                "path": relative_path,
                "message": "Libro seleccionado",
            }
        ),
        200,
    )


@app.route("/books", methods=["DELETE"])
def delete_book():
    data = request.json or {}
    path = data.get("path")
    try:
        resolved_path = resolve_upload_path(path)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    if not os.path.exists(resolved_path) or not os.path.isfile(resolved_path):
        return jsonify({"error": "El archivo especificado no existe."}), 404

    try:
        os.remove(resolved_path)
    except OSError as exc:
        logger.exception("No se pudo eliminar el archivo")
        return jsonify({"error": f"No se pudo eliminar el archivo: {exc}"}), 500

    if session.get("book_path") == resolved_path:
        session.pop("book_path", None)
        session.pop("book_title", None)

    relative_path = os.path.join(app.config["UPLOAD_FOLDER"], os.path.basename(resolved_path))
    return jsonify({"success": True, "message": "Libro eliminado", "path": relative_path}), 200


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
        if result.get("usage"):
            response_payload["usage"] = result.get("usage")
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
                    "usage": result.get("usage"),
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


@app.route("/generate-image", methods=["POST"])
def generate_image():
    try:
        data = request.json or {}
        prompt = (data.get("prompt") or "").strip()
        if not prompt:
            return jsonify({"error": "El prompt de la imagen está vacío."}), 400

        age = data.get("age", 9)
        fragment = (data.get("fragment") or "").strip()

        book_content = load_book_text()
        metadata = get_book_metadata()

        orchestrator = get_orchestrator()
        result = orchestrator.handle(
            {
                "mode": "imagen",
                "prompt": prompt,
                "age": age,
                "fragment": fragment,
                "book_text": book_content,
                "book_title": metadata.get("title"),
            }
        )

        image_payload = result.get("image") or {}
        image_data = image_payload.get("data")
        if not image_data:
            return jsonify({"error": "No se recibió la imagen generada."}), 500

        mime_type = image_payload.get("mime_type", "image/png")
        data_url = f"data:{mime_type};base64,{image_data}"
        timestamp = datetime.utcnow().isoformat() + "Z"

        response_payload = {
            "image": {
                "data_url": data_url,
                "mime_type": mime_type,
                "width": image_payload.get("width"),
                "height": image_payload.get("height"),
                "timestamp": timestamp,
                "prompt": result.get("prompt"),
                "revised_prompt": result.get("revised_prompt"),
                "fragment": result.get("fragment"),
            },
            "trace": result.get("trace"),
            "usage": result.get("usage"),
        }
        return jsonify(response_payload), 200

    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except FileNotFoundError as exc:
        return jsonify({"error": str(exc)}), 400
    except EnvironmentError as exc:
        return jsonify({"error": str(exc)}), 500
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Error en /generate-image")
        return jsonify({"error": f"Error al generar imagen: {exc}"}), 500


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
