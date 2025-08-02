import asyncio
import uuid
from typing import Dict, Optional

from app.tool.base import BaseTool, ToolResult

# Global storage outside of class to avoid Pydantic issues
_pending_requests: Dict[str, asyncio.Future] = {}
_task_manager: Optional[object] = None


class AskHuman(BaseTool):
    """Add a tool to ask human for help via web interface."""

    name: str = "ask_human"
    description: str = "Use this tool to ask human for help via web interface."
    parameters: str = {
        "type": "object",
        "properties": {
            "inquire": {
                "type": "string",
                "description": "The question you want to ask human.",
            }
        },
        "required": ["inquire"],
    }

    @classmethod
    def set_task_manager(cls, task_manager):
        """Set the task manager instance for sending events to frontend."""
        global _task_manager
        _task_manager = task_manager
        print(
            f"DEBUG: AskHuman.set_task_manager вызван, task_manager: {task_manager is not None}"
        )
        if task_manager:
            print(
                f"DEBUG: TaskManager ID: {getattr(task_manager, '_current_task_id', 'не установлен')}"
            )

    @classmethod
    async def provide_response(cls, request_id: str, response: str) -> bool:
        """Provide a response to a pending human request."""
        global _pending_requests
        if request_id in _pending_requests:
            future = _pending_requests[request_id]
            if not future.done():
                future.set_result(response)
                del _pending_requests[request_id]
                return True
        return False

    async def execute(self, inquire: str) -> str:
        global _task_manager, _pending_requests

        print(
            f"DEBUG: ask_human.execute вызван, _task_manager: {_task_manager is not None}"
        )
        if _task_manager:
            print(
                f"DEBUG: current_task_id: {getattr(_task_manager, '_current_task_id', 'не установлен')}"
            )

        if not _task_manager:
            # Fallback to console if no task manager is set
            return input(f"""Bot: {inquire}\n\nYou: """).strip()

        # Generate unique request ID
        request_id = str(uuid.uuid4())

        # Create a future to wait for the response
        response_future = asyncio.Future()
        _pending_requests[request_id] = response_future

        # Get current task ID from the task manager (assuming it's available)
        # We need to find a way to get the current task ID
        current_task_id = getattr(_task_manager, "_current_task_id", None)

        if current_task_id:
            # Send structured data for frontend via SSE
            await _task_manager.queues[current_task_id].put(
                {
                    "type": "ask_human",
                    "step": 0,
                    "result": {"question": inquire, "request_id": request_id},
                }
            )

            # Also send a log message for server logs
            await _task_manager.update_task_step(
                current_task_id,
                0,
                f"Question sent to user: {inquire}",
                "log",
            )

        try:
            # Wait for the response (with timeout)
            response = await asyncio.wait_for(
                response_future, timeout=300.0
            )  # 5 minutes timeout
            return response
        except asyncio.TimeoutError:
            # Clean up pending request
            if request_id in _pending_requests:
                del _pending_requests[request_id]
            return "Timeout: No response received from user within 5 minutes"
        except Exception as e:
            # Clean up pending request
            if request_id in _pending_requests:
                del _pending_requests[request_id]
            return f"Error waiting for user response: {str(e)}"
