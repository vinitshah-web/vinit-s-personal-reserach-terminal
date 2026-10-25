"""Tunnel keepalive daemon to ensure public URL remains active."""
import subprocess
import time
import sys

# Configure utf-8 stdout on Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def run_tunnel():
    while True:
        try:
            print("[Tunnel Daemon] Launching localtunnel on port 8000...")
            proc = subprocess.Popen(["npx", "--yes", "localtunnel", "--port", "8000"])
            proc.wait()
        except Exception as e:
            print(f"[Tunnel Daemon] Error: {e}")
        time.sleep(3)

if __name__ == "__main__":
    run_tunnel()
