import os
import sys
import posixpath
import paramiko

HOST = "124.43.28.106"
PORT = 22081
USER = "mwdep"
PASS = "Jaf@@mw1291"
REMOTE_DIR = "/JPL_MW/JPL-IOT-MIDDLEWARE"

EXCLUDE_DIRS = {".git", ".pytest_cache", "__pycache__", "venv", "logs", "scratch", ".gemini", ".idea", ".vscode"}
EXCLUDE_FILES = {".cdc_state.json", "apply_fix.py", "download_from_server.py", "deploy_to_server.py", "credential.txt"}

def upload_directory(sftp, local_dir, remote_dir):
    for root, dirs, files in os.walk(local_dir):
        # Filter directories
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith(".")]

        rel_dir = os.path.relpath(root, local_dir)
        if rel_dir == ".":
            target_remote_dir = remote_dir
        else:
            target_remote_dir = posixpath.join(remote_dir, rel_dir.replace("\\", "/"))

        try:
            sftp.stat(target_remote_dir)
        except IOError:
            print(f"Creating remote directory: {target_remote_dir}", flush=True)
            sftp.mkdir(target_remote_dir)

        for f in files:
            if f in EXCLUDE_FILES or f.endswith(".pyc"):
                continue
            local_path = os.path.join(root, f)
            remote_path = posixpath.join(target_remote_dir, f)
            print(f"Uploading: {rel_dir}/{f} -> {remote_path}", flush=True)
            sftp.put(local_path, remote_path)

def main():
    print(f"Connecting to SSH server {HOST}:{PORT} as {USER}...", flush=True)
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, port=PORT, username=USER, password=PASS, timeout=15)

    try:
        sftp = client.open_sftp()
        print("Uploading updated files via SFTP...", flush=True)
        upload_directory(sftp, ".", REMOTE_DIR)
        sftp.close()
        print("File upload completed successfully!", flush=True)

        # Ensure data and logs directories have proper write permissions
        print("Ensuring remote permissions on data and logs...", flush=True)
        client.exec_command(f"mkdir -p {REMOTE_DIR}/data {REMOTE_DIR}/logs && chmod -R 777 {REMOTE_DIR}/data {REMOTE_DIR}/logs")

        # Rebuild and restart docker container on remote server
        print("\nRebuilding and restarting Docker container on remote server...", flush=True)
        rebuild_cmd = f"cd {REMOTE_DIR} && docker-compose down && docker-compose build && docker-compose up -d"
        stdin, stdout, stderr = client.exec_command(rebuild_cmd, get_pty=True)

        for line in iter(stdout.readline, ""):
            print(line, end="", flush=True)
        
        err = stderr.read().decode("utf-8", errors="replace")
        if err:
            print("STDERR:", err, flush=True)

        # Allow container to initialize
        import time
        print("\nWaiting 5s for service container to initialize...", flush=True)
        time.sleep(5)

        # Check docker status
        print("\nChecking running docker containers...", flush=True)
        stdin, stdout, stderr = client.exec_command(f"cd {REMOTE_DIR} && docker ps")
        print(stdout.read().decode("utf-8", errors="replace"), flush=True)

        # Check container logs
        print("\nChecking latest container logs...", flush=True)
        stdin, stdout, stderr = client.exec_command(f"cd {REMOTE_DIR} && docker logs --tail 30 jpl-iot-middleware")
        print(stdout.read().decode("utf-8", errors="replace"), flush=True)

    finally:
        client.close()

if __name__ == "__main__":
    main()
