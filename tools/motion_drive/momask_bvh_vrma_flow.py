import json
import os
import time

import aiohttp

with open("/Users/bytedance/Desktop/explore_tech/agent_repo/agent_core/tools/motion_drive/motion_config.json", "r") as f:
    config = json.load(f)

async def from_text_to_bvh(text_prompt: str) -> str:
    motion_gen_path = config.get("motion_gen_path")
    save_path = config.get("vrma_file_download_local_path", "./")

    # Ensure save directory exists
    os.makedirs(save_path, exist_ok=True)

    async with aiohttp.ClientSession() as session:
        async with session.post(motion_gen_path, json={"text_prompt": text_prompt}) as resp:
            if resp.status == 200:
                bvh_content = await resp.text()

                timestamp = int(time.time() * 1000)
                filename = f"motion_{timestamp}.bvh"
                file_path = os.path.join(save_path, filename)

                with open(file_path, "w") as f:
                    f.write(bvh_content)

                return file_path
            else:
                raise Exception(f"Failed to generate BVH file: {resp.status} {await resp.text()}")


async def from_bvh_to_vrma(bvh_file_path: str, motion_name: str) -> str:
    # 获取配置的转换器路径，默认为本地主机
    vrma_converter_path = config.get("vrma_converter_path", "http://localhost")
    save_path = config.get("vrma_file_download_local_path", "./")

    # 确保保存目录存在
    os.makedirs(save_path, exist_ok=True)

    # 1. 上传BVH文件
    filename = os.path.basename(bvh_file_path)
    upload_url = f"{vrma_converter_path}/api/convert-bvh?filename={filename}&scale=0.01"

    try:
        # 读取BVH文件内容
        with open(bvh_file_path, "r") as f:
            bvh_content = f.read()

        async with aiohttp.ClientSession() as session:
            # 发送上传请求
            async with session.post(
                    upload_url,
                    headers={"Content-Type": "text/plain"},
                    data=bvh_content
            ) as resp:
                if resp.status == 200:
                    # 获取token
                    token = await resp.text()
                    print(f"BVH上传成功，获取到token: {token}")
                else:
                    raise Exception(f"BVH上传失败: {resp.status} {await resp.text()}")

            # 2. 下载VRMA文件
            download_url = json.loads(token)["url"]
            async with session.get(download_url) as resp:
                if resp.status == 200:
                    # 生成唯一的VRMA文件名
                    timestamp = int(time.time() * 1000)
                    vrma_filename = f"{motion_name}.vrma"
                    vrma_file_path = os.path.join(save_path, vrma_filename)

                    # 保存VRMA文件
                    with open(vrma_file_path, "wb") as f:
                        while True:
                            chunk = await resp.content.read(1024)
                            if not chunk:
                                break
                            f.write(chunk)

                    print(f"VRMA文件下载成功，保存路径: {vrma_file_path}")
                    return vrma_file_path
                else:
                    raise Exception(f"VRMA下载失败: {resp.status} {await resp.text()}")
    except Exception as e:
        raise Exception(f"转换BVH到VRMA失败: {str(e)}")


async def from_text_to_vrma(text_prompt: str) -> str:
    bvh_file_path = await from_text_to_bvh(text_prompt)
    motion_name = text_prompt.replace(" ", "_")
    await from_bvh_to_vrma(bvh_file_path, motion_name)
    return motion_name

if __name__ == "__main__":
    # test bvh2vrma flow
    import asyncio
    path = asyncio.run(from_bvh_to_vrma("/Users/bytedance/Desktop/explore_tech/agent_repo/agent_core/tools/motion_drive/pick_something_up_from_ground.bvh"
                                 , "pick_something_up_from_ground"))

    print(path)
    # test text2vrma flow
    # asyncio.run(from_text_to_vrma("a person is walking"))
