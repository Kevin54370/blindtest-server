import asyncio
import os
import secrets
import string
import time
from typing import Dict, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI(title="BlindTest Pro Server", version="1.2.0")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
PLAYER_GRACE_SECONDS = 2 * 60 * 60  # 2 heures pour retrouver le même joueur

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class Room:
    def __init__(self, code: str):
        self.code = code
        # Les joueurs déconnectés sont conservés temporairement pour permettre
        # une reconnexion avec le même identifiant et conserver leur score côté animateur.
        self.players: Dict[str, dict] = {}
        self.hosts: Dict[str, WebSocket] = {}
        self.locked = False
        self.winner: Optional[dict] = None
        self.created_at = time.time()
        self.lock = asyncio.Lock()

    def public_state(self):
        return {
            "type": "state",
            "room": self.code,
            "locked": self.locked,
            "winner": self.winner,
            "players": [
                {
                    "id": pid,
                    "name": p["name"],
                    "connected": p.get("ws") is not None,
                }
                for pid, p in self.players.items()
            ],
        }


rooms: Dict[str, Room] = {}


class CreateRoomRequest(BaseModel):
    code: Optional[str] = None


def normalize_room(code: str) -> str:
    return "".join(ch for ch in code.upper().strip() if ch.isalnum())[:12]


def make_room_code(length: int = 4) -> str:
    alphabet = string.digits
    for _ in range(100):
        code = "".join(secrets.choice(alphabet) for _ in range(length))
        if code not in rooms:
            return code
    raise RuntimeError("Unable to generate room code")


async def send_json_safe(ws: WebSocket, data: dict):
    try:
        await ws.send_json(data)
        return True
    except Exception:
        return False


async def broadcast(room: Room, data: dict):
    # Ne pas supprimer une inscription parce qu'un téléphone est temporairement
    # endormi ou inaccessible. La fermeture sera traitée par son propre handler.
    for player in list(room.players.values()):
        ws = player.get("ws")
        if ws is not None:
            if not await send_json_safe(ws, data):
                if player.get("ws") is ws:
                    player["ws"] = None
                    player["disconnected_at"] = time.time()

    for hid, ws in list(room.hosts.items()):
        if not await send_json_safe(ws, data):
            room.hosts.pop(hid, None)


async def broadcast_state(room: Room):
    await broadcast(room, room.public_state())


@app.get("/")
async def home():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/play")
async def play():
    return FileResponse(os.path.join(STATIC_DIR, "game.html"))


@app.get("/host")
async def host():
    return FileResponse(os.path.join(STATIC_DIR, "host.html"))


@app.get("/health")
async def health():
    return JSONResponse({"status": "ok", "rooms": len(rooms)})


@app.post("/api/rooms")
async def create_room(body: CreateRoomRequest):
    code = normalize_room(body.code or "") or make_room_code()
    if code in rooms:
        raise HTTPException(status_code=409, detail="Room already exists")
    rooms[code] = Room(code)
    return {"room": code}


@app.get("/api/rooms/{code}")
async def room_info(code: str):
    code = normalize_room(code)
    room = rooms.get(code)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    return room.public_state()


@app.delete("/api/rooms/{code}")
async def delete_room(code: str):
    code = normalize_room(code)
    room = rooms.pop(code, None)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    await broadcast(room, {"type": "room_closed"})
    return {"ok": True}


@app.websocket("/ws/player/{code}/{name}")
async def player_ws(websocket: WebSocket, code: str, name: str, player_id: Optional[str] = None):
    code = normalize_room(code)
    name = name.strip()[:30] or "Joueur"

    room = rooms.get(code)
    if not room:
        await websocket.close(code=4404, reason="Room not found")
        return

    await websocket.accept()

    # Reprendre l'inscription existante si le navigateur a conservé son identifiant.
    player = room.players.get(player_id) if player_id else None
    if player is None:
        player_id = secrets.token_hex(12)
        player = {
            "name": name,
            "ws": websocket,
            "connected_at": time.time(),
            "disconnected_at": None,
        }
        room.players[player_id] = player
    else:
        previous_ws = player.get("ws")
        player["name"] = name or player["name"]
        player["ws"] = websocket
        player["disconnected_at"] = None
        # Une ancienne socket peut être restée ouverte si le réseau a basculé.
        if previous_ws is not None and previous_ws is not websocket:
            try:
                await previous_ws.close(code=4001, reason="Reconnected on another connection")
            except Exception:
                pass

    await websocket.send_json({
        "type": "welcome",
        "player_id": player_id,
        "room": code,
        "name": player["name"],
        "reconnected": bool(player.get("connected_at") and player.get("disconnected_at") is None and player.get("ever_connected", False)),
        "locked": room.locked,
        "winner": room.winner,
    })
    player["ever_connected"] = True
    await broadcast_state(room)

    try:
        while True:
            message = await websocket.receive_json()
            msg_type = message.get("type")

            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})

            elif msg_type == "buzz":
                async with room.lock:
                    # Ignorer les messages d'une ancienne connexion remplacée.
                    if room.players.get(player_id, {}).get("ws") is not websocket:
                        continue
                    if room.locked:
                        await websocket.send_json({
                            "type": "buzz_rejected",
                            "winner": room.winner,
                        })
                        continue

                    room.locked = True
                    room.winner = {
                        "player_id": player_id,
                        "name": player["name"],
                        "timestamp": time.time(),
                    }
                    await broadcast(room, {
                        "type": "buzz",
                        "winner": room.winner,
                    })
                    await broadcast_state(room)

    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        # Ne pas marquer hors ligne la nouvelle socket si l'ancienne se ferme.
        current = room.players.get(player_id)
        if current is not None and current.get("ws") is websocket:
            current["ws"] = None
            current["disconnected_at"] = time.time()
            await broadcast_state(room)


@app.websocket("/ws/host/{code}")
async def host_ws(websocket: WebSocket, code: str):
    code = normalize_room(code)
    room = rooms.get(code)

    if not room:
        await websocket.close(code=4404, reason="Room not found")
        return

    await websocket.accept()
    host_id = secrets.token_hex(6)
    room.hosts[host_id] = websocket

    await websocket.send_json({
        "type": "welcome_host",
        "room": code,
    })
    await websocket.send_json(room.public_state())

    try:
        while True:
            message = await websocket.receive_json()
            msg_type = message.get("type")

            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})

            elif msg_type == "reset":
                async with room.lock:
                    room.locked = False
                    room.winner = None
                await broadcast(room, {"type": "reset"})
                await broadcast_state(room)

            elif msg_type == "lock":
                async with room.lock:
                    room.locked = True
                await broadcast_state(room)

            elif msg_type == "unlock":
                async with room.lock:
                    room.locked = False
                    room.winner = None
                await broadcast(room, {"type": "reset"})
                await broadcast_state(room)

    except WebSocketDisconnect:
        pass
    finally:
        room.hosts.pop(host_id, None)


@app.on_event("startup")
async def cleanup_task_startup():
    async def cleanup():
        while True:
            await asyncio.sleep(60)
            now = time.time()
            for room in list(rooms.values()):
                expired = [
                    pid for pid, player in room.players.items()
                    if player.get("ws") is None
                    and player.get("disconnected_at") is not None
                    and now - player["disconnected_at"] > PLAYER_GRACE_SECONDS
                ]
                for pid in expired:
                    room.players.pop(pid, None)

            stale = [
                code for code, room in rooms.items()
                if not room.players
                and not room.hosts
                and now - room.created_at > 6 * 3600
            ]
            for code in stale:
                rooms.pop(code, None)

    asyncio.create_task(cleanup())
