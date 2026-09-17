from dotenv import load_dotenv
import os
load_dotenv()

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import json
import asyncio

from orchestrator import run_agent
from tools.profile_manager import read_profile, PROFILE_PATH

RATE_LIMIT = f"{os.getenv('RATE_LIMIT_PER_MINUTE', '10')}/minute"

limiter = Limiter(key_func=get_remote_address)
app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class RunRequest(BaseModel):
    task: str


@app.post("/run")
@limiter.limit(RATE_LIMIT)
async def run(request: Request, body: RunRequest):
    queue: asyncio.Queue = asyncio.Queue()

    async def emit(event_type: str, data: dict):
        await queue.put({"type": event_type, "data": data})

    async def agent_task():
        try:
            result = await run_agent(body.task, emit)
            await queue.put({"type": "done", "data": {"result": result}})
        except Exception as e:
            await queue.put({"type": "error", "data": {"message": str(e)}})
        finally:
            await queue.put(None)  # 結束信號

    asyncio.create_task(agent_task())

    async def stream():
        while True:
            item = await queue.get()
            if item is None:
                break
            yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )


@app.get("/debug/files")
async def debug_files():
    """
    診斷用端點：回報這個執行環境實際看到哪些知識庫/資料檔案，
    用來排查「本機正常、部署環境讀不到檔案」這類問題（例如 volume 掛載蓋掉了映像檔內容）。
    只列檔名，不回傳檔案內容。
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))

    def describe(rel_path: str):
        abs_path = os.path.join(base_dir, rel_path)
        if not os.path.isdir(abs_path):
            return {"path": abs_path, "exists": False, "files": []}
        return {
            "path": abs_path,
            "exists": True,
            "files": sorted(os.listdir(abs_path)),
        }

    return {
        "cwd": os.getcwd(),
        "base_dir": base_dir,
        "data/runbooks": describe("data/runbooks"),
        "skills/devops-skill/references": describe("skills/devops-skill/references"),
        "data/profile.md exists": os.path.exists(os.path.join(base_dir, "data", "profile.md")),
        "data/bento_history.md exists": os.path.exists(os.path.join(base_dir, "data", "bento_history.md")),
    }


@app.get("/profile")
async def get_profile():
    content = await read_profile()
    return PlainTextResponse(content)


class ProfileRequest(BaseModel):
    content: str


@app.post("/profile")
async def save_profile(body: ProfileRequest):
    with open(PROFILE_PATH, "w", encoding="utf-8") as f:
        f.write(body.content)
    return {"status": "ok"}


app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
