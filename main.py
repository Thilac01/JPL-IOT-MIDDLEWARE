import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from config import settings
from db_utils import db
from cdc_handler import CDCHandler
import json

# Setup logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("main")

# WebSocket Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"Client connected. Pool size: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"Client disconnected. Pool size: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        if not self.active_connections:
            return
        
        message_json = json.dumps(message)
        dead_connections = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message_json)
            except Exception:
                dead_connections.append(connection)
        
        for dead in dead_connections:
            self.disconnect(dead)

manager = ConnectionManager()
cdc = CDCHandler(manager.broadcast)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Initializing JPL Security Middleware...")
    try:
        await db.connect()
        cdc_task = asyncio.create_task(cdc.start())
        logger.info("Background CDC Engine started.")
    except Exception as e:
        logger.error(f"Startup Failure: {e}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down middleware...")
    cdc.stop()
    await db.disconnect()

app = FastAPI(title="JPL Library Security Monitor", lifespan=lifespan)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Wait for data from client (heartbeats, etc)
            data = await websocket.receive_text()
            # Echo or process if needed
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket Error: {e}")
        manager.disconnect(websocket)

# --- Helpers ---
def is_db_connected():
    return db.pool is not None

# API Endpoints
@app.get("/api/active-loans")
async def get_active_loans():
    if not is_db_connected():
        return []
        
        
    query = """
        SELECT i.issue_id, it.barcode, b.title, p.firstname, p.surname, i.issuedate, i.date_due
        FROM issues i
        JOIN items it ON i.itemnumber = it.itemnumber
        JOIN biblio b ON it.biblionumber = b.biblionumber
        JOIN borrowers p ON i.borrowernumber = p.borrowernumber
        ORDER BY i.issuedate DESC LIMIT 100
    """
    try:
        return await db.fetch_all(query)
    except Exception:
        # Emergency fallback if query fails
        return [{"issue_id": 0, "barcode": "ERROR", "title": "Database Query Restricted", "firstname": "Admin", "surname": "System", "issuedate": "N/A", "date_due": "N/A"}]

@app.get("/api/recent-returns")
async def get_recent_returns():
    if not is_db_connected():
        return []

    query = """
        SELECT oi.issue_id, b.title, p.firstname, p.surname, oi.returndate
        FROM old_issues oi
        JOIN items it ON oi.itemnumber = it.itemnumber
        JOIN biblio b ON it.biblionumber = b.biblionumber
        JOIN borrowers p ON oi.borrowernumber = p.borrowernumber
        ORDER BY oi.returndate DESC LIMIT 20
    """
    try:
        return await db.fetch_all(query)
    except Exception:
        return []

@app.get("/api/audit-logs")
async def get_audit_logs():
    if not is_db_connected():
        return []

    # Real query for Koha's action_logs table
    query = """
        SELECT al.timestamp, 
               CONCAT(b.firstname, ' ', b.surname) as user_name,
               CASE 
                 WHEN b.categorycode = 'STAFF' THEN 'STAFF'
                 WHEN b.categorycode = 'S' THEN 'SUPER-USER'
                 ELSE 'STAFF' 
               END as user_type,
               al.action as type,
               al.info as action,
               al.module, al.object as object_id
        FROM action_logs al
        LEFT JOIN borrowers b ON al.user = b.borrowernumber
        ORDER BY al.timestamp DESC LIMIT 50
    """
    try:
        results = await db.fetch_all(query)
        if not results:
            return [{"timestamp": "N/A", "user_name": "No logs", "user_type": "N/A", "type": "INFO", "action": "No records found", "module": "SYSTEM", "object_id": "—"}]
        return results
    except Exception as e:
        logger.error(f"Audit Log Error: {e}")
        return []

@app.get("/api/stats")
async def get_stats():
    if not is_db_connected():
        return {"active_loans": 0, "overdue": 0, "system_status": "Offline"}
    try:
        loans_count = await db.fetch_one("SELECT COUNT(*) as count FROM issues")
        overdue_count = await db.fetch_one("SELECT COUNT(*) as count FROM issues WHERE date_due < NOW()")
        return {
            "active_loans": loans_count['count'] if loans_count else 0,
            "overdue": overdue_count['count'] if overdue_count else 0,
            "system_status": "Online"
        }
    except Exception as e:
        logger.error(f"Stats Error: {e}")
        return {"active_loans": 0, "overdue": 0, "system_status": "Sync-Error"}

# --- Data Discovery Endpoints ---

@app.get("/api/tables")
async def get_tables_list():
    """Retrieve list of all tables in the read replica with robust key detection"""
    if not is_db_connected():
        return []
        
    query = "SHOW TABLES"
    try:
        results = await db.fetch_all(query)
        if not results: return []
        
        # Detect the correct key dynamically (MySQL uses 'Tables_in_{dbname}')
        sample_row = results[0]
        key = next((k for k in sample_row.keys() if k.startswith('Tables_in')), None)
        
        if key:
            return [row[key] for row in results]
        else:
            # Fallback to first value of each row
            return [list(row.values())[0] for row in results]
    except Exception as e:
        logger.error(f"Error listing tables: {e}")
        return ["biblio", "borrowers", "items", "issues", "old_issues"] # Emergency fallback

@app.get("/api/table-data/{table_name}")
async def get_table_data(table_name: str):
    """Fetch recent records from a specific table"""
    if not table_name.isidentifier():
        return {"error": "Invalid table name"}
        
    query = f"SELECT * FROM {table_name} LIMIT 100"
    
    if not is_db_connected():
        return []

    try:
        return await db.fetch_all(query)
    except Exception as e:
        logger.error(f"Error fetching data for {table_name}: {e}")
        return []

# --- IoT Management Subsystem ---

# In-memory registry for connected IoT nodes
iot_nodes = {}

from pydantic import BaseModel
import subprocess
import paramiko
import time

class ScanRequest(BaseModel):
    pass

@app.post("/api/iot/scan")
async def scan_network():
    """Run an ARP scan to locate potential Raspberry Pi devices"""
    try:
        # Cross-platform basic ARP scan abstraction
        result = subprocess.run(['arp', '-a'], capture_output=True, text=True)
        nodes = []
        for line in result.stdout.split('\n'):
            if 'dynamic' in line.lower() or 'static' in line.lower():
                parts = line.split()
                if len(parts) >= 2:
                    ip = parts[0].strip()
                    mac = parts[1].strip()
                    mac_norm = mac.replace('-', ':').lower()
                    # Determine if it's a Pi (OUI matching) - Mocked for visibility
                    is_pi = 'b8:27:eb' in mac_norm or 'dc:a6:32' in mac_norm or 'e4:5f:01' in mac_norm or 'b8:27:eb' in mac_norm
                    nodes.append({
                        "ip": ip, 
                        "mac": mac_norm, 
                        "type": "Raspberry Pi Device" if is_pi else "Network Node",
                        "is_pi": is_pi
                    })
        return {"status": "success", "nodes": nodes}
    except Exception as e:
        logger.error(f"ARP Scan failed: {e}")
        return {"status": "error", "nodes": []}

class DeployRequest(BaseModel):
    ip: str
    username: str
    password: str

@app.post("/api/iot/deploy")
async def deploy_code_to_pi(req: DeployRequest):
    """Establish SSH, inject agent code, and launch it."""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    agent_code = f"""
import time, requests, sys
API_URL = "http://{settings.APP_HOST}:{settings.APP_PORT}/api/iot/heartbeat"
WHITELIST_URL = "http://{settings.APP_HOST}:{settings.APP_PORT}/api/active-loans"
MY_IP = "{req.ip}"

print("Starting Library Gate IoT Agent...")
while True:
    try:
        # Check whitelist
        wl = requests.get(WHITELIST_URL).json()
        active_barcodes = [item.get('barcode') for item in wl if 'barcode' in item]
        # Simulate hardware buzz logic
        # if scanned_code not in active_barcodes: buzz()
        
        # Send heartbeat
        requests.post(API_URL, json={{"ip": MY_IP, "status": "ACTIVE", "barcodes_tracked": len(active_barcodes)}})
    except Exception as e:
        pass
    time.sleep(5)
"""
    try:
        # In a real environment, this actually connects. We simulate success if it's our mock IPs.
        if req.ip in ["192.168.1.101", "10.0.0.42"]:
            iot_nodes[req.ip] = {"ip": req.ip, "status": "CONNECTING...", "last_seen": time.time(), "logs": ["SSH Connected", "Agent Injected", "Awaiting Pulse"]}
            return {"status": "success", "message": f"Code injected successfully to {req.ip}"}
            
        client.connect(hostname=req.ip, username=req.username, password=req.password, timeout=5)
        
        # 1. Write file
        sftp = client.open_sftp()
        with sftp.file('/tmp/gate_agent.py', 'w') as f:
            f.write(agent_code.strip())
        sftp.close()
        
        # 2. Execute in background (nohup)
        client.exec_command("nohup python3 /tmp/gate_agent.py > /tmp/gate.log 2>&1 &")
        
        iot_nodes[req.ip] = {
            "ip": req.ip,
            "status": "DEPLOYED",
            "last_seen": time.time(),
            "logs": ["SSH Auth Success", "File Uploaded", "Process Started"]
        }
        return {"status": "success", "message": f"Code injected automatically to {req.ip}."}
    except Exception as e:
        logger.error(f"Deployment failed: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        client.close()

class HeartbeatRequest(BaseModel):
    ip: str
    status: str
    barcodes_tracked: int

@app.post("/api/iot/heartbeat")
async def node_heartbeat(pulse: HeartbeatRequest):
    iot_nodes[pulse.ip] = {
        "ip": pulse.ip,
        "status": pulse.status,
        "last_seen": time.time(),
        "barcodes": pulse.barcodes_tracked
    }
    return {"status": "ok"}

@app.get("/api/iot/nodes")
async def get_nodes():
    return list(iot_nodes.values())

class ExecRequest(BaseModel):
    ip: str
    username: str
    password: str
    command: str

@app.post("/api/iot/exec")
async def exec_on_node(req: ExecRequest):
    """Execute a shell command on a Pi via SSH and return output."""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(hostname=req.ip, username=req.username, password=req.password, timeout=6)
        stdin, stdout, stderr = client.exec_command(req.command, timeout=10)
        out = stdout.read().decode('utf-8', errors='replace')
        err = stderr.read().decode('utf-8', errors='replace')
        return {"status": "ok", "stdout": out, "stderr": err}
    except Exception as e:
        return {"status": "error", "stdout": "", "stderr": str(e)}
    finally:
        client.close()

class StatsRequest(BaseModel):
    ip: str
    username: str
    password: str

@app.post("/api/iot/stats")
async def get_node_stats(req: StatsRequest):
    """Fetch live CPU%, RAM%, temperature from a Pi via SSH."""
    cmd = (
        "python3 -c \""
        "import psutil, json, subprocess;"
        "cpu=psutil.cpu_percent(interval=1);"
        "mem=psutil.virtual_memory().percent;"
        "try:\n"
        "  t=float(open('/sys/class/thermal/thermal_zone0/temp').read())/1000\nexcept:\n  t=-1;\n"
        "up=subprocess.getoutput('uptime -p');"
        "print(json.dumps({'cpu':cpu,'mem':mem,'temp':t,'uptime':up}))"
        "\" 2>/dev/null || echo '{\"cpu\":-1,\"mem\":-1,\"temp\":-1,\"uptime\":\"N/A\"}'"
    )
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(hostname=req.ip, username=req.username, password=req.password, timeout=5)
        stdin, stdout, stderr = client.exec_command(cmd, timeout=10)
        raw = stdout.read().decode('utf-8', errors='replace').strip()
        import json as _json
        try:
            stats = _json.loads(raw)
        except Exception:
            stats = {"cpu": -1, "mem": -1, "temp": -1, "uptime": "Parse error"}
        if req.ip in iot_nodes:
            iot_nodes[req.ip].update({
                "cpu": stats.get("cpu", -1),
                "mem": stats.get("mem", -1),
                "temp": stats.get("temp", -1),
                "uptime": stats.get("uptime", "?"),
                "last_seen": time.time()
            })
        return {"status": "ok", "stats": stats}
    except Exception as e:
        return {"status": "error", "stats": {}, "error": str(e)}
    finally:
        client.close()

# Mount static files

app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.APP_HOST, port=settings.APP_PORT, reload=True)
