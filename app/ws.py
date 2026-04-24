from fastapi import WebSocket, WebSocketDisconnect
from typing import List, Dict, Set
import json
import asyncio

import logging
logger = logging.getLogger(__name__)

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
        self.active_connections[str(user_id)] = websocket
        logger.info(f"WebSocket connected: user_id={user_id}. Active pool: {list(self.active_connections.keys())}")

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

    async def broadcast(self, message: dict):
        """Alias for convenience and possible future multi-node support."""
        await self.broadcast_local(message)

    async def send_personal_message(self, user_id: str, message: dict):
        """Send message only to a specific user if they are connected."""
        u_id = str(user_id)
        if u_id in self.active_connections:
            try:
                await self.active_connections[u_id].send_text(json.dumps(message))
                logger.info(f"WebSocket message sent to user_id={u_id}: type={message.get('type')}")
            except Exception as e:
                logger.error(f"Failed to send personal message to {u_id}: {str(e)}")
        else:
            logger.warning(f"WebSocket message target user_id={u_id} not connected. Pool: {list(self.active_connections.keys())}")

manager = ConnectionManager()
