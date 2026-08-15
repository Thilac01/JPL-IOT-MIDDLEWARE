import sys
import paramiko

HOST = "124.43.28.106"
PORT = 22081
USER = "mwdep"
PASS = "Jaf@@mw1291"

if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

def run_remote_command(cmd, cwd="/JPL_MW/JPL-IOT-MIDDLEWARE"):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(HOST, port=PORT, username=USER, password=PASS, timeout=10)
        full_cmd = f"cd {cwd} && {cmd}" if cwd else cmd
        stdin, stdout, stderr = client.exec_command(full_cmd)
        out = stdout.read().decode('utf-8', errors='replace')
        err = stderr.read().decode('utf-8', errors='replace')
        return out, err
    finally:
        client.close()

def sftp_read(remote_path):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(HOST, port=PORT, username=USER, password=PASS, timeout=10)
        sftp = client.open_sftp()
        with sftp.open(remote_path, "r") as f:
            return f.read().decode("utf-8")
    finally:
        client.close()

def sftp_write(remote_path, content):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(HOST, port=PORT, username=USER, password=PASS, timeout=10)
        sftp = client.open_sftp()
        with sftp.open(remote_path, "w") as f:
            f.write(content.encode("utf-8") if isinstance(content, str) else content)
    finally:
        client.close()

if __name__ == "__main__":
    cmd = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "ls -la"
    out, err = run_remote_command(cmd)
    if out:
        print(out)
    if err:
        print("STDERR:", err, file=sys.stderr)
