from fastapi import WebSocket, WebSocketDisconnect
from typing import List, Dict, Set
import json
import asyncio

class ConnectionManager:
    def __init__(self):
        # Maps user_id to their active websocket (local to this node)
        self.active_connections: Dict[str, WebSocket] = {}
        # Maps case_id to a set of user_ids currently viewing it
        self.rooms: Dict[str, Set[str]] = {}
        # Channel for cross-node communication
        self.pubsub_channel = "bgvms_presence"

    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        self.active_connections[user_id] = websocket

    async def disconnect(self, websocket: WebSocket, user_id: str):
        if user_id in self.active_connections:
            del self.active_connections[user_id]
        
        # Remove from all rooms
        for room_id in list(self.rooms.keys()):
            if user_id in self.rooms[room_id]:
                self.rooms[room_id].remove(user_id)
                await self.publish_presence(room_id)

    async def join_room(self, user_id: str, case_id: str):
        if case_id not in self.rooms:
            self.rooms[case_id] = set()
        self.rooms[case_id].add(user_id)
        await self.publish_presence(case_id)

    async def leave_room(self, user_id: str, case_id: str):
        if case_id in self.rooms and user_id in self.rooms[case_id]:
            self.rooms[case_id].remove(user_id)
            await self.publish_presence(case_id)

    async def publish_presence(self, case_id: str):
        """Broadcast room update to local connections."""
        viewers = list(self.rooms.get(case_id, []))
        message = {
            "type": "PRESENCE_UPDATE",
            "case_id": case_id,
            "viewers": viewers
        }
        await self.broadcast_local(message)

    async def broadcast_local(self, message: dict):
        """Broadcast to all connections on THIS server node."""
        msg_str = json.dumps(message)
        dead_users = []
        for user_id, socket in self.active_connections.items():
            try:
                await socket.send_text(msg_str)
            except Exception:
                dead_users.append((user_id, socket))
        
        for uid, s in dead_users:
            await self.disconnect(s, uid)

manager = ConnectionManager()
