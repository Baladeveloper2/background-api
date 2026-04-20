from fastapi import WebSocket, WebSocketDisconnect
from typing import List, Dict, Set
import json

class ConnectionManager:
    def __init__(self):
        # Maps user_id to their active websocket
        self.user_sockets: Dict[str, WebSocket] = {}
        # Maps case_id to a set of user_ids currently viewing it
        self.rooms: Dict[str, Set[str]] = {}
        # Maps websocket to user_id for cleanup
        self.socket_to_user: Dict[WebSocket, str] = {}

    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        self.user_sockets[user_id] = websocket
        self.socket_to_user[websocket] = user_id

    async def disconnect(self, websocket: WebSocket):
        user_id = self.socket_to_user.get(websocket)
        if user_id:
            # Remove from all rooms
            for room_id in list(self.rooms.keys()):
                if user_id in self.rooms[room_id]:
                    self.rooms[room_id].remove(user_id)
                    await self.broadcast_room_update(room_id)
            
            if user_id in self.user_sockets:
                del self.user_sockets[user_id]
            if websocket in self.socket_to_user:
                del self.socket_to_user[websocket]

    async def join_room(self, user_id: str, case_id: str):
        if case_id not in self.rooms:
            self.rooms[case_id] = set()
        self.rooms[case_id].add(user_id)
        await self.broadcast_room_update(case_id)

    async def leave_room(self, user_id: str, case_id: str):
        if case_id in self.rooms and user_id in self.rooms[case_id]:
            self.rooms[case_id].remove(user_id)
            await self.broadcast_room_update(case_id)

    async def broadcast_room_update(self, case_id: str):
        viewers = list(self.rooms.get(case_id, []))
        message = {
            "type": "PRESENCE_UPDATE",
            "case_id": case_id,
            "viewers": viewers # List of user IDs
        }
        await self.broadcast(message)

    async def broadcast(self, message: dict):
        # Global broadcast for simple compatibility or specific updates
        dead_sockets = []
        for user_id, socket in self.user_sockets.items():
            try:
                await socket.send_text(json.dumps(message))
            except Exception:
                dead_sockets.append(socket)
        
        for s in dead_sockets:
            await self.disconnect(s)

manager = ConnectionManager()
