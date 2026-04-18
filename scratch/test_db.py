import pymysql
import os
from dotenv import load_dotenv
from sshtunnel import SSHTunnelForwarder

load_dotenv()

def test_connection():
    ssh_host = os.getenv("SSH_HOST")
    ssh_user = os.getenv("SSH_USER")
    ssh_pass = "JPL@#lib260219a"
    
    db_user = os.getenv("REPLICA_USER")
    db_pass = "JPL@#lib260219a"
    
    print(f"Testing SSH Tunnel to {ssh_host}...")
    try:
        with SSHTunnelForwarder(
            (ssh_host, 22),
            ssh_username=ssh_user,
            ssh_password=ssh_pass,
            remote_bind_address=('127.0.0.1', 3306)
        ) as tunnel:
            print(f"Tunnel open on port {tunnel.local_bind_port}")
            conn = pymysql.connect(
                host='127.0.0.1',
                port=tunnel.local_bind_port,
                user=db_user,
                password=db_pass
            )
            print("Successfully connected to MySQL!")
            cur = conn.cursor()
            cur.execute("SHOW DATABASES")
            dbs = cur.fetchall()
            print("Databases:")
            for db in dbs:
                print(f" - {db[0]}")
            conn.close()
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    test_connection()
