import asyncio
import os
import subprocess
import time
from pathlib import Path
from src.infrastructure.logging.logger import get_logger


async def run_all():
    BASE_DIR = Path(__file__).resolve().parent
    CONFIG_DIR = BASE_DIR / "config"

    env = os.environ.copy()
    env["CORE_CONFIG_FILE"] = str(CONFIG_DIR / "core.json")
    env["MCP_CONFIG_FILE"] = str(CONFIG_DIR / "mcp_server.json")
    env["APP_LOG_DIR"] = str(BASE_DIR / "logs")

    logger = get_logger()

    state = False
    mcp_example_service = None
    mcp_hub_service = None
    main_service = None
    client_dev_service = None

    try:
        # ---- 1. MCP Example Server ----
        mcp_example_service = subprocess.Popen(
            ["python3", "tools/mcp_hub/mcp_server/terminal_mcp_server.py"],
            cwd=str(BASE_DIR), env=env
        )
        logger.info("mcp_example_service 已启动")
        time.sleep(3)

        # ---- 2. MCP Hub Server ----
        mcp_hub_service = subprocess.Popen(
            ["python3", "tools/mcp_hub/mcp_center_server.py", "--config", str(CONFIG_DIR / "mcp_server.json")],
            cwd=str(BASE_DIR), env=env
        )
        logger.info("mcp_hub_service 已启动")
        time.sleep(3)

        # ---- 3. Main Backend Service ----
        # back_end.py 在 lifespan 中会自动根据 core.json 的 danmaku_config.enabled
        # 决定是否启动弹幕桥接 + B站直播客户端，无需额外进程
        main_service = subprocess.Popen(
            ["python3", "src/main/back_end.py"],
            cwd=str(BASE_DIR), env=env
        )
        logger.info("主服务已启动（弹幕桥接由 danmaku_config.enabled 控制）")

        # ---- 4. Frontend Dev Server (可选) ----
        client_dir = BASE_DIR / "client"
        if (client_dir / "node_modules").exists():
            client_dev_service = subprocess.Popen(
                ["npx", "vite", "--host", "0.0.0.0"],
                cwd=str(client_dir), env=env
            )
            logger.info("前端 dev server 已启动")

        logger.info("全部服务启动完毕，按 Ctrl+C 停止")
        state = True

    except Exception as e:
        logger.exception("服务启动失败")
        state = False

    if state:
        services = {
            "main_service": main_service,
            "mcp_hub_service": mcp_hub_service,
            "mcp_example_service": mcp_example_service,
            "client_dev_service": client_dev_service,
        }

        try:
            main_service.wait()
        except KeyboardInterrupt:
            logger.info("正在停止所有服务...")
            for name, proc in services.items():
                if proc and proc.poll() is None:
                    logger.info(f"  停止 {name} (pid={proc.pid})")
                    proc.terminate()
            for name, proc in services.items():
                if proc:
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        logger.warning(f"  强制终止 {name}")
                        proc.kill()
            logger.info("所有服务已停止")


if __name__ == "__main__":
    asyncio.run(run_all())
