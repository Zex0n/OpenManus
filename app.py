import asyncio
import json
import os
import sqlite3
import threading
import tomllib
import uuid
import webbrowser
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime
from functools import partial
from json import dumps
from pathlib import Path

from fastapi import Body, Cookie, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
    StreamingResponse,
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from app.database import add_task, get_all_tasks
from app.database import get_task as db_get_task
from app.database import init_db, update_task

DB_PATH = "app_data.db"


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_db()
    yield
    # Shutdown (if needed)


app = FastAPI(lifespan=lifespan)


app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Task(BaseModel):
    id: str
    prompt: str
    created_at: datetime
    status: str
    steps: list = []

    def model_dump(self, *args, **kwargs):
        data = super().model_dump(*args, **kwargs)
        data["created_at"] = self.created_at.isoformat()
        return data


class TaskManager:
    def __init__(self):
        self.tasks = {}
        self.queues = {}
        self._current_task_id = None  # Track current task for ask_human

    def create_task(self, prompt: str) -> Task:
        task_id = str(uuid.uuid4())
        task = Task(
            id=task_id, prompt=prompt, created_at=datetime.now(), status="pending"
        )
        self.tasks[task_id] = task
        self.queues[task_id] = asyncio.Queue()
        add_task(task)
        return task

    async def update_task_step(
        self, task_id: str, step: int, result: str, step_type: str = "step"
    ):
        if task_id in self.tasks:
            task = self.tasks[task_id]
            task.steps.append({"step": step, "result": result, "type": step_type})
            await self.queues[task_id].put(
                {"type": step_type, "step": step, "result": result}
            )
            await self.queues[task_id].put(
                {"type": "status", "status": task.status, "steps": task.steps}
            )
            update_task(task_id, status=task.status, steps=task.steps)

    async def complete_task(self, task_id: str):
        if task_id in self.tasks:
            task = self.tasks[task_id]
            task.status = "completed"
            await self.queues[task_id].put(
                {"type": "status", "status": task.status, "steps": task.steps}
            )
            await self.queues[task_id].put({"type": "complete"})
            # Сохраняем финальный результат (последний шаг типа result)
            result = ""
            for s in reversed(task.steps):
                if s.get("type") == "result":
                    result = s.get("result", "")
                    break
            update_task(task_id, status=task.status, steps=task.steps, result=result)

    async def fail_task(self, task_id: str, error: str):
        if task_id in self.tasks:
            self.tasks[task_id].status = f"failed: {error}"
            await self.queues[task_id].put({"type": "error", "message": error})
            update_task(task_id, status=f"failed: {error}")


task_manager = TaskManager()

SERVER_PASSWORD = None


@app.get("/", response_class=HTMLResponse)
async def index(request: Request, auth: str = Cookie(default=None)):
    if auth != SERVER_PASSWORD:
        return templates.TemplateResponse(
            "login.html", {"request": request}, status_code=401
        )
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/download")
async def download_file(file_path: str):
    base_dir = os.path.abspath("workspace")
    abs_path = os.path.abspath(os.path.join(base_dir, file_path))
    if not abs_path.startswith(base_dir + os.sep):
        raise HTTPException(status_code=403, detail="Access denied")
    if not os.path.exists(abs_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(abs_path, filename=os.path.basename(abs_path))


@app.post("/tasks")
async def create_task(prompt: str = Body(..., embed=True)):
    task = task_manager.create_task(prompt)
    asyncio.create_task(run_task(task.id, prompt))
    return {"task_id": task.id}


from app.agent.manus import Manus


async def run_task(task_id: str, prompt: str):
    try:
        task_manager.tasks[task_id].status = "running"
        task_manager._current_task_id = task_id  # Set current task for ask_human

        agent = Manus(
            name="Manus",
            description="A versatile agent that can solve various tasks using multiple tools",
        )

        async def on_think(thought):
            await task_manager.update_task_step(task_id, 0, thought, "think")

        async def on_tool_execute(tool, input):
            await task_manager.update_task_step(
                task_id, 0, f"Executing tool: {tool}\nInput: {input}", "tool"
            )

        async def on_action(action):
            await task_manager.update_task_step(
                task_id, 0, f"Executing action: {action}", "act"
            )

        async def on_run(step, result):
            await task_manager.update_task_step(task_id, step, result, "run")

        from app.logger import logger

        class SSELogHandler:
            def __init__(self, task_id):
                self.task_id = task_id

            async def __call__(self, message):
                import re

                # Extract - Subsequent Content
                cleaned_message = re.sub(r"^.*? - ", "", message)

                event_type = "log"
                if "✨ Manus's thoughts:" in cleaned_message:
                    event_type = "think"
                elif "🛠️ Manus selected" in cleaned_message:
                    event_type = "tool"
                elif "🎯 Tool" in cleaned_message:
                    event_type = "act"
                elif "📝 Oops!" in cleaned_message:
                    event_type = "error"
                elif "🏁 Special tool" in cleaned_message:
                    event_type = "complete"

                await task_manager.update_task_step(
                    self.task_id, 0, cleaned_message, event_type
                )

        sse_handler = SSELogHandler(task_id)
        logger.add(sse_handler)

        # Initialize ask_human tool with task manager
        from app.tool.ask_human import AskHuman

        AskHuman.set_task_manager(task_manager)
        print(f"DEBUG: TaskManager установлен для ask_human, task_id: {task_id}")

        result = await agent.run(prompt)
        await task_manager.update_task_step(task_id, 1, result, "result")
        await task_manager.complete_task(task_id)
    except Exception as e:
        await task_manager.fail_task(task_id, str(e))
    finally:
        # Clear current task
        if task_manager._current_task_id == task_id:
            task_manager._current_task_id = None


@app.get("/tasks/{task_id}/events")
async def task_events(task_id: str):
    async def event_generator():
        if task_id not in task_manager.queues:
            yield f"event: error\ndata: {dumps({'message': 'Task not found'})}\n\n"
            return

        queue = task_manager.queues[task_id]

        task = task_manager.tasks.get(task_id)
        if task:
            yield f"event: status\ndata: {dumps({'type': 'status', 'status': task.status, 'steps': task.steps})}\n\n"

        while True:
            try:
                event = await queue.get()
                formatted_event = dumps(event)

                yield ": heartbeat\n\n"

                if event["type"] == "complete":
                    yield f"event: complete\ndata: {formatted_event}\n\n"
                    break
                elif event["type"] == "error":
                    yield f"event: error\ndata: {formatted_event}\n\n"
                    break
                elif event["type"] == "step":
                    task = task_manager.tasks.get(task_id)
                    if task:
                        yield f"event: status\ndata: {dumps({'type': 'status', 'status': task.status, 'steps': task.steps})}\n\n"
                    yield f"event: {event['type']}\ndata: {formatted_event}\n\n"
                elif event["type"] in ["think", "tool", "act", "run", "ask_human"]:
                    yield f"event: {event['type']}\ndata: {formatted_event}\n\n"
                else:
                    yield f"event: {event['type']}\ndata: {formatted_event}\n\n"

            except asyncio.CancelledError:
                print(f"Client disconnected for task {task_id}")
                break
            except Exception as e:
                print(f"Error in event stream: {str(e)}")
                yield f"event: error\ndata: {dumps({'message': str(e)})}\n\n"
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/tasks")
async def get_tasks():
    db_tasks = get_all_tasks()
    # decorate steps/result
    for t in db_tasks:
        try:
            t["steps"] = json.loads(t["steps"]) if t["steps"] else []
        except Exception:
            t["steps"] = []
    return JSONResponse(
        content=db_tasks,
        headers={"Content-Type": "application/json"},
    )


@app.get("/tasks/{task_id}")
async def get_task(task_id: str):
    t = db_get_task(task_id)
    if not t:
        raise HTTPException(status_code=404, detail="Task not found")
    try:
        t["steps"] = json.loads(t["steps"]) if t["steps"] else []
    except Exception:
        t["steps"] = []
    return t


# @app.get("/config/status")
# async def check_config_status():
#     config_path = Path(__file__).parent / "config" / "config.toml"
#     example_config_path = Path(__file__).parent / "config" / "config.example.toml"
#
#     if config_path.exists():
#         try:
#             with open(config_path, "rb") as f:
#                 current_config = tomllib.load(f)
#             return {"status": "exists", "config": current_config}
#         except Exception as e:
#             return {"status": "error", "message": str(e)}
#     elif example_config_path.exists():
#         try:
#             with open(example_config_path, "rb") as f:
#                 example_config = tomllib.load(f)
#             return {"status": "missing", "example_config": example_config}
#         except Exception as e:
#             return {"status": "error", "message": str(e)}
#     else:
#         return {"status": "no_example"}


@app.post("/config/save")
async def save_config(config_data: dict = Body(...)):
    try:
        config_dir = Path(__file__).parent / "config"
        config_dir.mkdir(exist_ok=True)

        config_path = config_dir / "config.toml"

        toml_content = ""

        if "llm" in config_data:
            toml_content += "# Global LLM configuration\n[llm]\n"
            llm_config = config_data["llm"]
            for key, value in llm_config.items():
                if key != "vision":
                    if isinstance(value, str):
                        toml_content += f'{key} = "{value}"\n'
                    else:
                        toml_content += f"{key} = {value}\n"

        if "server" in config_data:
            toml_content += "\n# Server configuration\n[server]\n"
            server_config = config_data["server"]
            for key, value in server_config.items():
                if isinstance(value, str):
                    toml_content += f'{key} = "{value}"\n'
                else:
                    toml_content += f"{key} = {value}\n"

        with open(config_path, "w", encoding="utf-8") as f:
            f.write(toml_content)

        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500, content={"message": f"Server error: {str(exc)}"}
    )


def open_local_browser(config):
    webbrowser.open_new_tab(f"http://{config['host']}:{config['port']}")


def load_config():
    global SERVER_PASSWORD
    try:
        config_path = Path(__file__).parent / "config" / "config.toml"
        print("config_path", config_path)

        if not config_path.exists():
            print("1")
            SERVER_PASSWORD = "changeme"
            return {"host": "localhost", "port": 5172}

        with open(config_path, "rb") as f:
            config = tomllib.load(f)

        SERVER_PASSWORD = config["server"].get("password", "changeme")
        return {"host": config["server"]["host"], "port": config["server"]["port"]}
    except FileNotFoundError:
        print("2")
        SERVER_PASSWORD = "changeme"
        return {"host": "localhost", "port": 5172}
    except KeyError as e:
        print(
            f"The configuration file is missing necessary fields: {str(e)}, use default configuration"
        )
        SERVER_PASSWORD = "changeme"
        return {"host": "localhost", "port": 5172}


@app.post("/tasks/{task_id}/respond")
async def respond_to_human_request(task_id: str, data: dict = Body(...)):
    """Handle user response to ask_human requests."""
    request_id = data.get("request_id")
    response = data.get("response")

    if not request_id or response is None:
        raise HTTPException(
            status_code=400, detail="request_id and response are required"
        )

    # Import AskHuman and provide the response
    from app.tool.ask_human import AskHuman

    success = await AskHuman.provide_response(request_id, response)

    if success:
        return {"success": True, "message": "Response delivered"}
    else:
        raise HTTPException(
            status_code=404, detail="Request not found or already completed"
        )


@app.post("/login")
async def login(data: dict = Body(...)):
    password = data.get("password")
    if password == SERVER_PASSWORD:
        response = JSONResponse({"success": True})
        response.set_cookie(key="auth", value=SERVER_PASSWORD, httponly=True)
        return response
    return JSONResponse(
        {"success": False, "error": "Incorrect password"}, status_code=401
    )


if __name__ == "__main__":
    import uvicorn

    init_db()

    config = load_config()
    print(config)
    open_with_config = partial(open_local_browser, config)
    threading.Timer(3, open_with_config).start()
    uvicorn.run(app, host=config["host"], port=config["port"])
