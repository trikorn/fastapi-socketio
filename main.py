from fastapi import FastAPI
import socketio

fastapi_app = FastAPI()

sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=[],  # set your frontend origins in production
)

# Combine into a single ASGI app
app = socketio.ASGIApp(sio, other_asgi_app=fastapi_app)

@fastapi_app.get("/health")
async def health():
    return {"ok": True}