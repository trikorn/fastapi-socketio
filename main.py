from fastapi import FastAPI
import socketio
from typing import Dict
from dataclasses import dataclass

fastapi_app = FastAPI()

sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=[],  # set frontend origins here
)

# Combine into a single ASGI app
app = socketio.ASGIApp(sio, other_asgi_app=fastapi_app)

@fastapi_app.get("/health")
async def health():
    return {"ok": True}

@dataclass
class Player:
    sid: str
    name: str

players: Dict[str, Player] = {}  # sid -> Player

@sio.event
async def connect(sid, environ, auth):
    # auth is whatever the client sends in Socket.IO handshake
    # Example: auth = {"name": "Alice"}
    name = (auth or {}).get("name") or f"guest-{sid[:5]}"
    players[sid] = Player(sid=sid, name=name)

    await sio.enter_room(sid, "lobby")
    await sio.emit("lobby:joined", {"sid": sid, "name": name}, room=sid)
    await sio.emit("lobby:presence", {"event": "join", "sid": sid, "name": name}, room="lobby")

@sio.event
async def disconnect(sid):
    p = players.pop(sid, None)
    if p:
        await sio.emit("lobby:presence", {"event": "leave", "sid": sid, "name": p.name}, room="lobby")