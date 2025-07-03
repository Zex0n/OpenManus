import asyncio
import json
import os
from queue import Queue

from flask import Blueprint, Response, jsonify, request, stream_with_context
from flask_cors import cross_origin

from app.config import config
from webserver.backend.src.core.manus_processor import (
    process_prompt,
    process_prompt_stream,
)

chat_bp = Blueprint("chat", __name__)


class OpenManusAgent:
    def _run_openmanus_command(self, prompt):
        try:
            result = asyncio.run(process_prompt(prompt))
            return (
                result
                if result
                else f"OpenManus processed the request: '{prompt}'. Task execution result is ready."
            )

        except Exception as e:
            return f"Error when executing the request: {str(e)}"

    def process_message(self, message):
        result = self._run_openmanus_command(message)
        # Split the result into steps if it's a string
        if isinstance(result, str):
            steps = result.split("\n")
            return [
                {"type": "step", "content": step.strip()}
                for step in steps
                if step.strip()
            ]
        return [{"type": "step", "content": str(result)}]


agent = OpenManusAgent()


@chat_bp.route("/chat", methods=["POST"])
@cross_origin()
def chat():
    try:
        data = request.get_json()

        if not data or "message" not in data:
            return jsonify({"error": "Message not found"}), 400

        user_message = data["message"].strip()

        if not user_message:
            return jsonify({"error": "Empty message"}), 400

        response = agent.process_message(user_message)
        # response = [{"type": "step", "content": "TEST MESSAGE"}]

        return jsonify({"response": response, "status": "success"})

    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}", "status": "error"}), 500


from flask import Response, stream_with_context


@chat_bp.route("/chat/stream", methods=["POST"])
@cross_origin()
def chat_stream():
    data = request.get_json()
    user_message = data.get("message", "").strip()
    if not user_message:
        return jsonify({"error": "Empty message"}), 400

    def generate():
        # Здесь обычный (НЕ async) генератор!
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        async_gen = process_prompt_stream(user_message)
        try:
            while True:
                step = loop.run_until_complete(async_gen.__anext__())
                yield f"data: {json.dumps({'type': 'step', 'content': step})}\n\n"
        except StopAsyncIteration:
            pass

    return Response(stream_with_context(generate()), mimetype="text/event-stream")


# @chat_bp.route("/chat/status", methods=["GET"])
# @cross_origin()
# def chat_status():
#     return jsonify(
#         {
#             "openmanus_path": agent.openmanus_path,
#             "status": "ready",
#         }
#     )


# @chat_bp.route("/chat/api_info", methods=["GET"])
# @cross_origin()
# def chat_api_info():
#     # Get host and port from config.toml
#     backend_cfg = getattr(config, "backend", None)
#     if backend_cfg:
#         host = getattr(backend_cfg, "host", "0.0.0.0")
#         port = getattr(backend_cfg, "port", 5000)
#     else:
#         host = "0.0.0.0"
#         port = 5000
#     return jsonify({"host": host, "port": port})
