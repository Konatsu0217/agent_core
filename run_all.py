import asyncio
import os
import shutil
import subprocess
import time
import traceback
from pathlib import Path
from utils.logger import get_logger


async def run_all():
    BASE_DIR = Path(__file__).resolve().parent
    CONFIG_DIR = BASE_DIR / "config"

    env = os.environ.copy()
    env["CORE_CONFIG_FILE"] = str(CONFIG_DIR / "core.json")
    env["MCP_CONFIG_FILE"] = str(CONFIG_DIR / "mcp_servers.json")
    env["APP_LOG_DIR"] = str(BASE_DIR / "logs")

    logger = get_logger()

    state = False
    mcp_example_service = None
    pe_service = None
    mcp_hub_service = None
    pe_service = None
    main_service = None

    try:
        mcp_example_service = subprocess.Popen(["python3", "tools/mcp_hub/mcp_servers/mcp_server_example.py"],
                                       cwd=str(BASE_DIR), env=env)

        logger.info("mcp_example_service 已启动")
        time.sleep(3)

        pe_service = subprocess.Popen(["python3", "tools/pe_server/main.py"], cwd=str(BASE_DIR), env=env)

        logger.info("pe_service 已启动")
        time.sleep(3)

        mcp_hub_service = subprocess.Popen(
        ["python3", "tools/mcp_hub/mcp_center_server.py", "--config", str(CONFIG_DIR / "mcp_servers.json")],
        cwd=str(BASE_DIR), env=env)

        logger.info("mcp_hub_service 已启动")
        time.sleep(3)

        main_service = subprocess.Popen(["python3", "main.py"], cwd=str(BASE_DIR), env=env)

        logger.info("主服务已启动，全部启动完毕，按Ctrl+C停止")

        logger.info("正在启动前端....")
        webui_service = None
        webui_dir = BASE_DIR / "webUI"
        frontend_cmd = None
        for cmd in (["npm", "run", "dev"], ["pnpm", "dev"], ["yarn", "dev"]):
            if shutil.which(cmd[0]):
                frontend_cmd = cmd
                break
        if frontend_cmd is None:
            raise RuntimeError("未找到可用的包管理器：npm/pnpm/yarn")
        webui_service = subprocess.Popen(frontend_cmd, cwd=str(webui_dir), env=env)
        logger.info("webUI 已启动: http://localhost:5173/")
        state = True

    except Exception as e:
        logger.exception("服务启动失败")

    if state:
        try:
            # 等待进程结束，或者我们可以做其他事情
            main_service.wait()
            pe_service.wait()
            mcp_hub_service.wait()
            mcp_example_service.wait()
            webui_service.wait()
        except KeyboardInterrupt:
            logger.info("正在停止服务...")
            if main_service and main_service.poll() is None:
                main_service.terminate()
            if pe_service and pe_service.poll() is None:
                pe_service.terminate()
            if mcp_hub_service and mcp_hub_service.poll() is None:
                mcp_hub_service.terminate()
            if mcp_example_service and mcp_example_service.poll() is None:
                mcp_example_service.terminate()
            if webui_service and webui_service.poll() is None:
                webui_service.terminate()
            main_service.wait()
            pe_service.wait()
            mcp_hub_service.wait()
            mcp_example_service.wait()
            if webui_service:
                webui_service.wait()
            logger.info("服务已停止")

if __name__ == "__main__":
    asyncio.run(run_all())
