import os
import subprocess
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CONFIG_DIR = BASE_DIR / "config"

env = os.environ.copy()
env["CORE_CONFIG_FILE"] = str(CONFIG_DIR / "core.json")
env["MCP_CONFIG_FILE"] = str(CONFIG_DIR / "mcp_servers.json")

mcp_example_service = subprocess.Popen(["python3", "tools/mcp_hub/mcp_servers/mcp_server_example.py"], cwd=str(BASE_DIR), env=env)

print(f"mcp_example_service 已启动")
time.sleep(3)

pe_service = subprocess.Popen(["python3", "tools/pe_server/main.py"], cwd=str(BASE_DIR), env=env)

print(f"pe_service 已启动")
time.sleep(3)

mcp_hub_service = subprocess.Popen(["python3", "tools/mcp_hub/mcp_center_server.py", "--config", str(CONFIG_DIR / "mcp_servers.json")], cwd=str(BASE_DIR), env=env)

print(f"mcp_hub_service 已启动")
time.sleep(3)

# main_server = subprocess.Popen(["python", "main.py"])
#
# print(f"主服务已启动，全部启动完毕，按Ctrl+C停止")

try:
    # 等待进程结束，或者我们可以做其他事情
    # main_server.wait()
    pe_service.wait()
    mcp_hub_service.wait()
    mcp_example_service.wait()
except KeyboardInterrupt:
    print("正在停止服务...")
    # main_server.terminate()
    pe_service.terminate()
    mcp_hub_service.terminate()
    mcp_example_service.terminate()
    # main_server.wait()
    pe_service.wait()
    mcp_hub_service.wait()
    mcp_example_service.wait()
    print("服务已停止")
