# FastAPI + Socket.IO Game Server

This project is a minimal **FastAPI** + **Socket.IO** backend intended for small multi‑user games.
It exposes a basic HTTP health check and a Socket.IO server that:

- Keeps track of connected players
- Manages a **lobby** where everyone starts
- Provides a simple **matchmaking queue** (2 players per match)
- Maintains per‑match game state and broadcasts updates

You can plug your own game logic into the existing `match_input` handler.

---

## Requirements

Install the Python dependencies from `requirements.txt` (Python 3.10+ recommended; tested with Python 3.12):

```bash
pip install -r requirements.txt
```

The main libraries are:

- `fastapi`
- `uvicorn[standard]`
- `python-socketio[asgi]`
- `pydantic`
- `redis` (optional, for future scaling / persistence)

---

## Running the server

From the project root (`/home/me/Documents/test/fastapi-socketio`):

```bash
uvicorn main:app --reload
```

This will start the ASGI app (FastAPI + Socket.IO) on `http://127.0.0.1:8000` by default.

### Health check

You can confirm the HTTP side is working:

```bash
curl http://127.0.0.1:8000/health
```

Expected response:

```json
{"ok": true}
```

---

## Socket.IO endpoints and events

The Socket.IO server is attached to the same ASGI app. A typical JavaScript client (browser) setup might look like:

```js
const socket = io("http://127.0.0.1:8000", {
  transports: ["websocket"],     // recommended
  auth: { name: "Player1" },    // optional name sent on connect
});

socket.on("connect", () => {
  console.log("connected", socket.id);
});

socket.on("lobby:joined", (data) => {
  console.log("Joined lobby:", data);
});

socket.on("lobby:presence", (evt) => {
  console.log("Lobby presence event:", evt);
});

socket.on("match:found", (data) => {
  console.log("Match found:", data);
});

socket.on("match:state", (data) => {
  console.log("Match state:", data);
});

socket.on("match:ended", (data) => {
  console.log("Match ended:", data);
});

socket.on("match:error", (err) => {
  console.error("Match error:", err);
});
```

### Connect

- **Event**: implicit on Socket.IO connection
- **Auth payload** (optional): `{ "name": "Alice" }`
- **Server behavior**:
  - Registers a `Player` for the current `sid`
  - Adds the client to the `lobby` room
  - Emits:
    - `lobby:joined` to that client
    - `lobby:presence` (`event: "join"`) to the `lobby` room

### Disconnect

- **Event**: implicit when the client disconnects
- **Server behavior**:
  - Removes the player
  - Removes them from the matchmaking queue (if queued)
  - If they are in an active match:
    - Emits `match:ended` with `reason: "disconnect"` to the match room
    - Moves the remaining player(s) back to the `lobby`
  - Emits `lobby:presence` (`event: "leave"`) to the `lobby` room

### Matchmaking: `match_find`

- **Client emits**:

  ```js
  socket.emit("match_find");
  ```

- **Server behavior**:
  - If the player is already queued or in a match, it does nothing
  - Otherwise, it adds the player to the matchmaking `queue`
  - When at least 2 players are queued:
    - Creates a new match with a unique `match_id` and room `match:{match_id}`
    - Moves both players from `lobby` to that match room
    - Emits to the match room:
      - `match:found` with `{ match_id, room }`
      - `match:state` with the initial state

### Match input: `match_input`

- **Client emits**:

  ```js
  socket.emit("match_input", {
    match_id: "<match-id-from-match_found>",
    action: { type: "move", x: 1, y: 2 },
  });
  ```

- **Server behavior** (simplified):
  - Validates payload shape
  - Ensures the match exists and the sender is in that match
  - Updates `state.turn` and appends to `state.log`
  - Emits updated `match:state` to the match room

You can replace the simple state update with your own game rules and state transitions.

---

## Customizing CORS

In `main.py` the Socket.IO server is created as:

```python
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",
)
```

For production, change `"*"` to a list of allowed origins, e.g.:

```python
cors_allowed_origins=["https://your-frontend.example.com"]
```