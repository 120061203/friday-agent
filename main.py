from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.responses import StreamingResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
import asyncio

from orchestrator import run_agent
from tools.profile_manager import read_profile, PROFILE_PATH

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class RunRequest(BaseModel):
    task: str


@app.post("/run")
async def run(body: RunRequest):
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
