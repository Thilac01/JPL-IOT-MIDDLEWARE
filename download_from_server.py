import os
import stat
import paramiko

HOST = "124.43.28.106"
PORT = 22081
USER = "mwdep"
PASS = "Jaf@@mw1291"

REMOTE_DIR = "/JPL_MW/JPL-IOT-MIDDLEWARE"
LOCAL_DIR = r"c:\Users\thila\OneDrive\Desktop\New folder (12)"

EXCLUDE_DIRS = {"venv", "__pycache__", ".pytest_cache", ".git"}
EXCLUDE_FILES = {}

def sftp_download_recursive(sftp, remote_dir, local_dir):
    os.makedirs(local_dir, exist_ok=True)
    
    for item in sftp.listdir_attr(remote_dir):
        if item.filename in EXCLUDE_DIRS:
            continue
        if item.filename in EXCLUDE_FILES:
            continue
            
        remote_path = f"{remote_dir}/{item.filename}"
        local_path = os.path.join(local_dir, item.filename)
        
        mode = item.st_mode
        if stat.S_ISDIR(mode):
            sftp_download_recursive(sftp, remote_path, local_path)
        else:
            try:
                print(f"Downloading: {item.filename} ({item.st_size} bytes)")
                sftp.get(remote_path, local_path)
            except Exception as e:
                print(f"Error downloading {item.filename}: {e}")

def main():
    print(f"Connecting to {HOST}:{PORT}...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(HOST, port=PORT, username=USER, password=PASS, timeout=15)
        sftp = client.open_sftp()
        print(f"Starting SCP/SFTP transfer from {REMOTE_DIR} -> {LOCAL_DIR}...")
        sftp_download_recursive(sftp, REMOTE_DIR, LOCAL_DIR)
        print("\nAll files successfully transferred to local PC!")
    finally:
        client.close()

if __name__ == "__main__":
    main()
