from collections import deque
from dataclasses import dataclass
from typing import Dict, List, Deque, Any
import uuid

from fastapi import FastAPI
import socketio


fastapi_app = FastAPI()

sio = socketio.AsyncServer(
    async_mode="asgi",
    # In dev you can use "*" and tighten this later.
    cors_allowed_origins="*",
)

# Combine into a single ASGI app
app = socketio.ASGIApp(sio, other_asgi_app=fastapi_app)


@fastapi_app.get("/health")
async def health() -> Dict[str, bool]:
    return {"ok": True}


@dataclass
class Player:
    sid: str
    name: str


players: Dict[str, Player] = {}  # sid -> Player
queue: Deque[str] = deque()
matches: Dict[str, Dict[str, Any]] = {}
# match_id -> {
#   "room": str,
#   "players": List[str],
#   "state": {...}
# }


@sio.event
async def connect(sid, environ, auth):
    # auth is whatever the client sends in Socket.IO handshake
    # Example: auth = {"name": "Alice"}
    name = (auth or {}).get("name") or f"guest-{sid[:5]}"
    players[sid] = Player(sid=sid, name=name)

    await sio.enter_room(sid, "lobby")
    await sio.emit("lobby:joined", {"sid": sid, "name": name}, room=sid)
    await sio.emit(
        "lobby:presence",
        {
            "event": "join",
            "sid": sid,
            "name": name,
        },
        room="lobby",
    )


@sio.event
async def disconnect(sid):
    # Remove from players map
    p = players.pop(sid, None)

    # Ensure the user is not left in the matchmaking queue
    try:
        queue.remove(sid)
    except ValueError:
        pass

    # If the player was in a match, end that match and move the opponent back to the lobby
    ended_matches: List[str] = []
    for match_id, match in list(matches.items()):
        if sid in match["players"]:
            room = match["room"]
            other_players = [psid for psid in match["players"] if psid != sid]

            await sio.emit(
                "match:ended",
                {
                    "match_id": match_id,
                    "reason": "disconnect",
                    "sid": sid,
                },
                room=room,
            )

            for other_sid in other_players:
                await sio.leave_room(other_sid, room)
                await sio.enter_room(other_sid, "lobby")

            ended_matches.append(match_id)

    for match_id in ended_matches:
        matches.pop(match_id, None)

    if p:
        await sio.emit(
            "lobby:presence",
            {
                "event": "leave",
                "sid": sid,
                "name": p.name,
            },
            room="lobby",
        )


@sio.event
async def match_find(sid):
    # Ignore if already queued or already in a match
    if sid in queue:
        return
    if any(sid in match["players"] for match in matches.values()):
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
                "log": [],
            },
        }

        for psid in [p1, p2]:
            await sio.leave_room(psid, "lobby")
            await sio.enter_room(psid, room)

        await sio.emit(
            "match:found",
            {
                "match_id": match_id,
                "room": room,
            },
            room=room,
        )
        await sio.emit(
            "match:state",
            {
                "match_id": match_id,
                "state": matches[match_id]["state"],
            },
            room=room,
        )


@sio.event
async def match_input(sid, data):
    """
    data example:
    { "match_id": "...", "action": {"type": "move", "x": 1, "y": 2} }
    """
    if not isinstance(data, dict):
        await sio.emit("match:error", {"error": "invalid_payload"}, room=sid)
        return

    match_id = data.get("match_id")
    action = data.get("action")

    if not match_id or match_id not in matches:
        await sio.emit("match:error", {"error": "unknown_match"}, room=sid)
        return

    match = matches[match_id]
    if sid not in match["players"]:
        await sio.emit("match:error", {"error": "not_in_match"}, room=sid)
        return

    if action is None:
        await sio.emit("match:error", {"error": "missing_action"}, room=sid)
        return

    # Apply action to server state (your game logic goes here)
    match["state"]["turn"] += 1
    match["state"]["log"].append({"by": sid, "action": action})

    await sio.emit(
        "match:state",
        {
            "match_id": match_id,
            "state": match["state"],
        },
        room=match["room"],
    )
