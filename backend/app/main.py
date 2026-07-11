from fastapi import FastAPI

from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.threads import router as threads_router

app = FastAPI(title="Internal Knowledge Agent")
app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(threads_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
