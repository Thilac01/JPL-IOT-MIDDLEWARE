# JPL Security & IoT Middleware: Technical Architecture

This document provides a comprehensive technical breakdown of the JPL Library Security Monitor and IoT Middleware system.

## 1. System Overview
The JPL Middleware is an industrial-grade synchronization layer designed to bridge a Koha ILS (Integrated Library System) with physical security hardware (RFID Gates) and real-time monitoring dashboards.

### Core Objectives:
*   **Real-Time Monitoring**: Instant detection of circulation events (Issues/Returns).
*   **Edge Connectivity**: Secure management of Raspberry Pi nodes at library exits.
*   **Multi-Channel Notifications**: Real-time WebSocket updates and SMTP email alerts.

---

## 2. High-Level Architecture

```mermaid
graph TD
    subgraph "External Shard (Koha)"
        DB[(MySQL Replica)]
        LOGS[[Binary Logs]]
    end

    subgraph "Middleware Core (Python/FastAPI)"
        SST[SSH Tunnel Manager]
        CDC[CDC handler - Binlog Reader]
        WSM[WebSocket Manager]
        SMTP[Notification Engine]
        API[REST API Layer]
    end

    subgraph "Clients & Devices"
        UI[Web Dashboard]
        IOT[Raspberry Pi Gates]
    end

    DB -->|Encapsulated| SST
    LOGS -->|Stream| CDC
    CDC -->|Broadcast| WSM
    CDC -->|Alerts| SMTP
    WSM -->|Real-time| UI
    API -->|Deploy/Control| IOT
    IOT -->|Heartbeat| API
```

---

## 3. Technical Stack
*   **Backend**: Python 3.10+ (FastAPI)
*   **Concurrency**: Asynchronous I/O (AsyncIO)
*   **Data Capture**: `python-mysql-replication` (BinLog streaming)
*   **Infrastructure**: `Paramiko` (SSH), `SSHTunnelForwarder`
*   **Frontend**: Vanilla JavaScript (ES6+), WebSocket API, CSS3 (Enterprise Aesthetics)

---

## 4. Subsystem Deep-Dives

### 4.1 Real-Time CDC Pipeline (Change Data Capture)
Unlike traditional polling (which is slow and high-overhead), this system uses a "push" model by monitoring the MySQL Binary Log.

**The Workflow:**
1.  A librarian issues a book in Koha.
2.  The MySQL database writes an `INSERT` row event to the `issues` table.
3.  The Middleware's **BinLogStreamReader** identifies the event across the SSH tunnel.
4.  The `CDCHandler` parses the raw bytes into a Python dictionary.
5.  **Broadcast**: The event is sent to the Frontend via WebSockets.
6.  **Notification**: The SMTP engine fires an email to the administrator.

### 4.2 IoT Node Deployment Engine
The system manages remote IoT gates via an automated injection pipeline:
1.  **ARP Scanner**: Scans the network to find Raspberry Pi devices (MAC OUI matching).
2.  **SSH Injection**: The Middleware connects to the Pi via SSH.
3.  **Agent Deployment**: A lightweight Python Agent is written to the Pi's `/tmp` directory.
4.  **Auto-Start**: The Middleware executes the agent as a background service (`nohup`).

---

## 5. Key Implementation Snippets

### 5.1 Real-Time Event Dispatch
Located in `cdc_handler.py`, this handles the conversion of database rows to UI alerts:
```python
async def handle_event(self, event):
    for row in event.rows:
        table = event.table.lower()
        if table == "issues" and event_type == "INSERT":
            alert = {"title": "📚 Book Checked Out!", "msg": f"Item issued to borrower."}
            await send_notification_email(alert['title'], alert['msg'])
            await self.broadcast_callback(alert)
```

### 5.2 Dynamic Topology Map
The frontend uses a relative-positioning engine to create the "Network Graph." When a node is dragged, it triggers a live recalculation of the SVG Bezier paths:
```javascript
function drawLines() {
    const p1 = outXY(koha_node);
    const p2 = inXY(mid_node);
    svg_path.setAttribute('d', `M ${p1.x} ${p1.y} C ${cx} ${p1.y}, ${cx} ${p2.y}, ${p2.x} ${p2.y}`);
}
```

---

## 6. Security & Infrastructure
*   **SSH Encapsulation**: ALL database traffic is tunneled through an encrypted SSH channel to 137.184.15.52. Local ports are bound dynamically to avoid conflicts.
*   **CORS Policy**: Configured strictly to allow middleware access only to authorized library origins.
*   **JWT Readiness**: The `auth.py` module is structured to support Bearer Tokens for future expansion.

---

## 7. Operational Flow Chart

```mermaid
sequenceDiagram
    participant K as Koha DB
    participant C as CDC Handler
    participant W as WebSocket
    participant D as Dashboard
    participant E as Email (SMTP)

    K->>C: Row Event (INSERT)
    C->>C: Parse Table Logic
    par UI Broadcast
        C->>W: Push Layout Update
        W->>D: Update Active Loans Table
    and Email Dispatch
        C->>E: Send SMTP via Brevo
        E-->>Admins: Real-time Alert
    end
```

© 2026 JPL Security Systems. All Technical Rights Reserved.


















<img width="1913" height="873" alt="IOT MAPS _2" src="https://github.com/user-attachments/assets/d303f54f-e2e3-4009-a9df-f96661cb545b" />
<img width="1916" height="881" alt="IOT MAPS _1" src="https://github.com/user-attachments/assets/c3127b38-7460-4f9e-8300-ef28c1223c83" />
<img width="1918" height="863" alt="DASHBOARD" src="https://github.com/user-attachments/assets/7eb1b224-ca7a-442a-a882-03863e1735c7" />
# JPL-IOT-MIDDLEWARE<img width="1906" height="862" alt="IOT MAPS" src="https://github.com/user-attachments/assets/5ca5c37a-e2f6-4897-831e-802bf6f105bf" />
<img width="1913" height="872" alt="WHITELIST" src="https://github.com/user-attachments/assets/59352ce6-ae5d-41ee-a177-35e28a113d46" />
<img width="1913" height="866" alt="LIVE TABLES" src="https://github.com/user-attachments/assets/55129419-d474-4843-b128-801387c25b31" />
<img width="1915" height="859" alt="image" src="https://github.com/user-attachments/assets/58b6150c-f02c-41a3-a87f-9704753c40e6" />
