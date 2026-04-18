import asyncio
import aiomysql
import os
from dotenv import load_dotenv
from sshtunnel import SSHTunnelForwarder

load_dotenv()

async def test_aiomysql():
    ssh_host = os.getenv("SSH_HOST")
    ssh_user = os.getenv("SSH_USER")
    ssh_pass = os.getenv("SSH_PASSWORD")
    
    db_user = os.getenv("REPLICA_USER")
    db_pass = os.getenv("REPLICA_PASSWORD")
    db_name = os.getenv("REPLICA_DB")
    
    print(f"Testing SSH Tunnel to {ssh_host}...")
    tunnel = SSHTunnelForwarder(
        (ssh_host, 22),
        ssh_username=ssh_user,
        ssh_password=ssh_pass,
        remote_bind_address=('127.0.0.1', 3306)
    )
    tunnel.start()
    
    try:
        print(f"Tunnel open on port {tunnel.local_bind_port}")
        conn = await aiomysql.connect(
            host='127.0.0.1',
            port=tunnel.local_bind_port,
            user=db_user,
            password=db_pass,
            db=db_name,
            connect_timeout=20
        )
        print("aiomysql: Successfully connected!")
        conn.close()
    except Exception as e:
        print(f"aiomysql: Failed: {e}")
    finally:
        tunnel.stop()

if __name__ == "__main__":
    asyncio.run(test_aiomysql())
