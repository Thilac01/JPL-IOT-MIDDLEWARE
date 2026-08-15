from remote_exec import sftp_read, sftp_write

path = "/JPL_MW/JPL-IOT-MIDDLEWARE/app/db/tunnel.py"
content = sftp_read(path)

old_str = "            settings.REPLICA_PORT = self.local_bind_port"
new_str = "            settings.REPLICA_HOST = \"127.0.0.1\"\n            settings.REPLICA_PORT = self.local_bind_port"

if old_str in content:
    content = content.replace(old_str, new_str)
    sftp_write(path, content)
    print("app/db/tunnel.py updated successfully.")
else:
    print("Pattern not found in tunnel.py")
