from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
import asyncio

from orchestrator import run_agent

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


app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
