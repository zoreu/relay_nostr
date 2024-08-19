import asyncio
import websockets
import json
import sqlite3
import hashlib

# Cria a conexão com o banco de dados SQLite
conn = sqlite3.connect('nostr_relay.db')
c = conn.cursor()

# Cria a tabela de eventos
c.execute('''CREATE TABLE IF NOT EXISTS events
             (id TEXT PRIMARY KEY, pubkey TEXT, created_at INTEGER, kind INTEGER, tags TEXT, content TEXT, sig TEXT)''')
conn.commit()

# Função para calcular o ID de um evento
def compute_event_id(event):
    event_serialized = [
        0,
        event['pubkey'],
        event['created_at'],
        event['kind'],
        event['tags'],
        event['content']
    ]
    event_json = json.dumps(event_serialized, separators=(',', ':'))
    event_id = hashlib.sha256(event_json.encode()).hexdigest()
    return event_id

# Função para processar eventos
async def process_event(event):
    event_id = compute_event_id(event)
    c.execute("INSERT OR IGNORE INTO events VALUES (?, ?, ?, ?, ?, ?, ?)", (
        event_id,
        event['pubkey'],
        event['created_at'],
        event['kind'],
        json.dumps(event['tags']),
        event['content'],
        event['sig']
    ))
    conn.commit()

# Função para manipular mensagens WebSocket
async def handle_message(websocket, message):
    msg = json.loads(message)
    if msg[0] == "EVENT":
        event = msg[1]
        await process_event(event)
        await websocket.send(json.dumps(["OK", event["id"], True, ""]))
    elif msg[0] == "REQ":
        subscription_id = msg[1]
        filters = msg[2:]
        # Recupera os eventos do banco de dados com base nos filtros
        for row in c.execute("SELECT * FROM events"):
            event = {
                "id": row[0],
                "pubkey": row[1],
                "created_at": row[2],
                "kind": row[3],
                "tags": json.loads(row[4]),
                "content": row[5],
                "sig": row[6]
            }
            await websocket.send(json.dumps(["EVENT", subscription_id, event]))

# Função principal do WebSocket
async def relay_server(websocket, path):
    async for message in websocket:
        await handle_message(websocket, message)

# Inicia o servidor WebSocket
start_server = websockets.serve(relay_server, "0.0.0.0", 8080)

# Executa o servidor
asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()
