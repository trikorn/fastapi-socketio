from fastapi import FastAPI
import socketio
from typing import Dict
from dataclasses import dataclass
import uuid
from collections import deque

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
    await sio.emit("lobby:presence", {
        "event": "join",
        "sid": sid,
        "name": name
    },
                   room="lobby")


@sio.event
async def disconnect(sid):
    p = players.pop(sid, None)
    if p:
        await sio.emit("lobby:presence", {
            "event": "leave",
            "sid": sid,
            "name": p.name
        },
                       room="lobby")


queue = deque()
matches = {
}  # match_id -> {"room": ..., "players": [sid1, sid2], "state": ...}


@sio.event
async def match_find(sid):
    if sid in queue:
        return
    queue.append(sid)

    # if we have at least 2 players, create a match
    if len(queue) >= 2:
        p1 = queue.popleft()
        p2 = queue.popleft()
        match_id = str(uuid.uuid4())
        room = f"match:{match_id}"

        matches[match_id] = {
            "room": room,
            "players": [p1, p2],
            "state": {
                "turn": 0,
                "log": []
            },
        }

        for psid in [p1, p2]:
            await sio.leave_room(psid, "lobby")
            await sio.enter_room(psid, room)

        await sio.emit("match:found", {
            "match_id": match_id,
            "room": room
        },
                       room=room)
        await sio.emit("match:state", {
            "match_id": match_id,
            "state": matches[match_id]["state"]
        },
                       room=room)
