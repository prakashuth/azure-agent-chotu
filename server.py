import os
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient

# Config via env
PROJECT_ENDPOINT = os.environ["PROJECT_ENDPOINT"]         # e.g. https://acct.services.ai.azure.com/api/projects/proj
AGENT_ID = os.environ["AGENT_ID"]                         # existing agent id in the project

app = FastAPI()
app.add_middleware(CORSOMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# In App Service, DefaultAzureCredential will use the app's Managed Identity automatically.
credential = DefaultAzureCredential()
project = AIProjectClient(endpoint=PROJECT_ENDPOINT, credential=credential)  # Entra-only auth. :contentReference[oaicite:2]{index=2}

class ChatReq(BaseModel):
    message: str

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/chat")
def chat(req: ChatReq):
    # One-shot: create thread + run, add user message, wait for result
    run = project.agents.create_thread_and_run(
        assistant_id=AGENT_ID,
        thread={"messages": [{"role": "user", "content": req.message}]},
    )
    # Poll until completed
    while True:
        r = project.agents.get_run(run.thread_id, run.id)
        if r.status in ("completed", "failed", "cancelled"):
            break
    if r.status != "completed":
        raise HTTPException(500, f"Run status: {r.status}")

    msgs = list(project.agents.list_messages(run.thread_id))
    last = msgs[0] if msgs else None
    text = last.content[0].text if (last and last.content and last.content[0].kind=="text") else ""
    return {"reply": text}
