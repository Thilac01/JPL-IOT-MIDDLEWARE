import logging
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, status
from app.core.security import verify_api_key
from app.services.iot_service import iot_service

logger = logging.getLogger("routers.iot")

router = APIRouter(tags=["IoT Device Management"])

# --- Request & Response Models ---

class ScanResponse(BaseModel):
    status: str
    nodes: List[Dict[str, Any]]

class DeployRequest(BaseModel):
    ip: str = Field(..., description="Target node IP address")
    username: str = Field(default="root", description="SSH username")
    password: Optional[str] = Field(default=None, description="SSH password")

class HeartbeatRequest(BaseModel):
    ip: str = Field(..., description="Reporting node IP address")
    status: str = Field(default="ACTIVE", description="Node status")
    barcodes_tracked: int = Field(default=0, description="Count of barcodes in whitelist")

class ExecRequest(BaseModel):
    ip: str = Field(..., description="Target node IP address")
    username: str = Field(default="root", description="SSH username")
    password: Optional[str] = Field(default=None, description="SSH password")
    command: str = Field(..., description="Shell command to execute")

class StatsRequest(BaseModel):
    ip: str = Field(..., description="Target node IP address")
    username: str = Field(default="root", description="SSH username")
    password: Optional[str] = Field(default=None, description="SSH password")

# --- Endpoints ---

@router.post("/api/iot/scan", response_model=ScanResponse, summary="Discover Network IoT Nodes")
async def scan_network(api_key: Optional[str] = Depends(verify_api_key)):
    """Run an ARP network discovery scan to locate Raspberry Pi and IoT gate devices."""
    try:
        nodes = await iot_service.scan_network()
        return {"status": "success", "nodes": nodes}
    except Exception as e:
        logger.error(f"ARP Scan failed: {e}")
        return {"status": "error", "nodes": []}

@router.post("/api/iot/deploy", summary="Deploy Edge Agent to IoT Node")
async def deploy_code_to_pi(req: DeployRequest, api_key: Optional[str] = Depends(verify_api_key)):
    """Establish SSH connection, inject lightweight gate agent, and start daemon."""
    result = await iot_service.deploy_agent(req.ip, req.username, req.password)
    return result

@router.post("/api/iot/heartbeat", summary="Record Node Heartbeat")
async def node_heartbeat(pulse: HeartbeatRequest):
    """Receive periodic heartbeat telemetry from remote IoT gate agents."""
    await iot_service.record_heartbeat(pulse.ip, pulse.status, pulse.barcodes_tracked)
    return {"status": "ok"}

@router.get("/api/iot/nodes", summary="List Connected IoT Nodes")
async def get_nodes():
    """Retrieve all registered IoT nodes with current status and metrics."""
    return await iot_service.get_all_nodes()

@router.post("/api/iot/exec", summary="Execute Remote SSH Command on Node")
async def exec_on_node(req: ExecRequest, api_key: Optional[str] = Depends(verify_api_key)):
    """Execute a shell command on an IoT node via SSH with timeout protection."""
    # Basic sanity check on command
    if not req.command or len(req.command) > 1000:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid command length")
    
    return await iot_service.execute_command(req.ip, req.username, req.password, req.command)

@router.post("/api/iot/stats", summary="Query Node Live CPU/RAM/Temp")
async def get_node_stats(req: StatsRequest, api_key: Optional[str] = Depends(verify_api_key)):
    """Query live CPU%, Memory%, thermal temperature, and uptime metrics from an IoT node."""
    return await iot_service.get_node_stats(req.ip, req.username, req.password)
