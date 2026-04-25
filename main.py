from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client, Client
import json
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket:WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()

@app.get("/")
async def health_check():
    return {"status": "online", "message": "Server is awake!"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)

    chat_history = supabase.table("messages").select("*").order("created_at").execute()
    await websocket.send_text(json.dumps({"type": "history",
                                          "data": chat_history.data}))

    try:
        while True:
            data = await websocket.receive_text()
            msg_json = json.loads(data)

            supabase.table("messages").insert({
                "sender": msg_json["user"],
                "text": msg_json["content"]
            }).execute()

            await manager.broadcast(json.dumps({
                "type": "new_message",
                "user": msg_json["user"],
                "content": msg_json["content"]
            }))

            await websocket.send_text(f"Server Received: {msg_json['content']}")

    except WebSocketDisconnect:
        print("Client left the chat")
        manager.disconnect(websocket)
