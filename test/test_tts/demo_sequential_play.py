#!/usr/bin/env python3
"""
TTS流式按顺序写入缓冲区播放测试脚本
支持边接收边播放，按顺序写入缓冲区
"""

import json
import time

import requests

from function_demo.demo_stream_audio_player import StreamingAudioPlayer


def test_streaming_sequential_play():
    """测试流式按顺序播放"""

    # 服务地址
    url = "http://localhost:8000/tts"

    # 测试请求数据
    test_data = {
        "index": 1,
        "text": "你好，这是一个测试语音合成服务，使用Edge TTS引擎进行流式输出，接下来我将朗读一段很长很长的文本。Nijisanji推动了Live2D模型的普及，取代了之前专注于3D模型的模式，并推动了直播方式的转变，而非像绊爱这样的VTuber惯用的剪辑视频和短片。Live2D是一种动画技术（不要与用于创建 Live2D 动画的软件（例如 Live2D Cubism）混淆），用于为静态图像（通常是动漫风格的角色）制作动画；模型由多个图层组成，保存为Photoshop文件（.psd 格式）。图层会分别移动，以展现角色的整体动画和表情，例如头部的倾斜。模型的部件可以很简单，例如脸部、头发和身体，也可以细致到眉毛、睫毛，甚至金属闪光等效果。复杂的模型会拥有数百个图层，可动图层会需要布点并三角网格化以使用ARAP等成熟的网格变形算法。",
        "engine": "edgetts",
        "voice": "default"
    }

    print("🚀 开始流式按顺序播放测试...")
    print(f"📤 请求数据: {json.dumps(test_data, ensure_ascii=False, indent=2)}")

    # 创建播放器
    player = StreamingAudioPlayer()

    try:
        # 记录开始时间
        start_time = time.time()

        # 启动播放线程
        player.is_playing = True
        player.is_receiving = True
        player.start_playback_thread()

        # 等待播放线程启动
        time.sleep(0.5)

        # 发送请求，启用流式响应
        print(f"📡 发送POST请求... time = {time.time()}")
        response = requests.post(url, json=test_data, stream=True, timeout=30)

        # 检查响应状态
        if response.status_code != 200:
            print(f"❌ 请求失败: {response.status_code}")
            print(f"错误信息: {response.text}")
            player.stop_playback()
            return False

        print(f"✅ 请求成功，状态码: {response.status_code}")
        print(f"📋 内容类型: {response.headers.get('content-type', 'unknown')}")

        # 获取音频索引
        audio_index = response.headers.get('X-Audio-Index')
        if audio_index:
            print(f"🔢 音频索引: {audio_index}")

        print("\n🎵 开始流式接收并按顺序播放...")
        print("=" * 60)

        # 逐块接收音频数据并按顺序添加到播放队列
        first_chunk_received = False

        for chunk in response.iter_content(chunk_size=player.chunk_size):
            if chunk:  # 过滤掉keep-alive块
                # 标记接收到第一个音频包
                if not first_chunk_received:
                    first_chunk_received = True
                    print(f"🎵 接收到第一个音频包: {len(chunk)} bytes")

                # 按顺序添加音频数据到播放队列
                player.add_audio_chunk(chunk)

        # 标记接收完成
        player.stop_receiving()

        print(f"\n📊 接收完成: {player.total_bytes / 1024:.1f} KB ({player.chunk_count} 块)")
        print(f"📊 播放队列: {player.audio_queue.qsize()} 块待播放")

        # 等待播放完成
        print("\n⏳ 等待播放完成...")
        player.wait_for_completion()

        # 记录结束时间
        end_time = time.time()
        duration = end_time - start_time

        print("\n" + "=" * 60)
        print(f"✅ 流式按顺序播放完成!")
        print(f"📈 总耗时: {duration:.2f} 秒")
        print(f"📦 总数据量: {player.total_bytes / 1024:.1f} KB")
        print(f"🧩 数据块数: {player.chunk_count}")
        print(f"⚡ 平均速度: {player.total_bytes / duration / 1024:.1f} KB/s")

        # # 保存完整音频文件（可选）
        # output_file = f"test_sequential_{test_data['index']}.mp3"
        #
        # # 重新获取完整音频数据用于保存
        # response_save = requests.post(url, json=test_data, timeout=30)
        # if response_save.status_code == 200:
        #     with open(output_file, 'wb') as f:
        #         f.write(response_save.content)
        #     print(f"💾 完整音频已保存: {output_file}")
        return True

    except requests.exceptions.Timeout:
        print("❌ 请求超时")
        player.stop_playback()
        return False
    except requests.exceptions.ConnectionError:
        print("❌ 连接失败，请确保TTS服务正在运行")
        player.stop_playback()
        return False
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        player.stop_playback()
        return False


if __name__ == "__main__":
    print("🎯 TTS流式按顺序播放测试工具")
    print("=" * 60)
    print("📝 本脚本支持边接收边按顺序播放音频")
    print("📝 确保播放顺序和接收顺序完全一致")
    print("=" * 60)

    # 运行流式按顺序播放测试
    success = test_streaming_sequential_play()

    if success:
        print("\n🎉 流式按顺序播放测试通过!")
    else:
        print("\n💥 流式按顺序播放测试失败!")

    print("\n✨ 测试完成")