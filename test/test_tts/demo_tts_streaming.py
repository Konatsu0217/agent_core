#!/usr/bin/env python3
"""
TTS服务测试脚本 - 测试edgetts引擎的流式输出
"""

import requests
import json
import time
import sys


def test_tts_streaming():
    """测试TTS流式输出"""

    # 服务地址
    url = "http://localhost:8000/tts"

    # 测试请求数据
    test_data = {
        "index": 1,
        "text": "你好，这是一个测试语音合成服务，使用Edge TTS引擎进行流式输出，接下来我将朗读一段很长很长的文本。Nijisanji推动了Live2D模型的普及，取代了之前专注于3D模型的模式，并推动了直播方式的转变，而非像绊爱这样的VTuber惯用的剪辑视频和短片。Live2D是一种动画技术（不要与用于创建 Live2D 动画的软件（例如 Live2D Cubism）混淆），用于为静态图像（通常是动漫风格的角色）制作动画；模型由多个图层组成，保存为Photoshop文件（.psd 格式）。图层会分别移动，以展现角色的整体动画和表情，例如头部的倾斜。模型的部件可以很简单，例如脸部、头发和身体，也可以细致到眉毛、睫毛，甚至金属闪光等效果。复杂的模型会拥有数百个图层，可动图层会需要布点并三角网格化以使用ARAP等成熟的网格变形算法。",
        "engine": "edgetts",
        "voice": "default"
    }

    print("🚀 开始测试TTS流式输出...")
    print(f"📤 请求数据: {json.dumps(test_data, ensure_ascii=False, indent=2)}")

    try:
        # 记录开始时间
        start_time = time.time()

        # 发送请求，启用流式响应
        response = requests.post(url, json=test_data, stream=True, timeout=30)

        # 检查响应状态
        if response.status_code != 200:
            print(f"❌ 请求失败: {response.status_code}")
            print(f"错误信息: {response.text}")
            return False

        print(f"✅ 请求成功，状态码: {response.status_code}")
        print(f"📋 响应头: {dict(response.headers)}")

        # 获取音频索引
        audio_index = response.headers.get('X-Audio-Index')
        if audio_index:
            print(f"🔢 音频索引: {audio_index}")

        # 准备保存音频文件
        output_file = f"test_tts_{test_data['index']}.mp3"
        total_bytes = 0
        chunk_count = 0

        print(f"💾 开始接收音频流，保存到: {output_file}")

        with open(output_file, 'wb') as f:
            # 逐块接收音频数据
            for chunk in response.iter_content(chunk_size=1024):  #
                if chunk:  # 过滤掉keep-alive块
                    f.write(chunk)
                    total_bytes += len(chunk)
                    chunk_count += 1

                    # 每收到10KB显示一次进度
                    if total_bytes % (10 * 1024) == 0:
                        print(f"📊 已接收: {total_bytes / 1024:.1f} KB ({chunk_count} 块)")

        # 记录结束时间
        end_time = time.time()
        duration = end_time - start_time

        print(f"✅ 音频流接收完成!")
        print(f"📈 总耗时: {duration:.2f} 秒")
        print(f"📦 总数据量: {total_bytes / 1024:.1f} KB")
        print(f"🧩 数据块数: {chunk_count}")
        print(f"⚡ 平均速度: {total_bytes / duration / 1024:.1f} KB/s")

        # 验证文件是否有效
        if total_bytes > 0:
            print(f"🎵 音频文件已生成: {output_file} ({total_bytes} 字节)")

            # 尝试播放音频（可选）
            try:
                import pygame
                pygame.mixer.init()
                pygame.mixer.music.load(output_file)
                
                # 获取音频长度（秒）
                audio_length = pygame.mixer.Sound(output_file).get_length()
                
                print(f"🔊 正在播放生成的音频...")
                print(f"⏱️  音频时长: {audio_length:.1f} 秒")
                
                pygame.mixer.music.play()
                
                # 等待音频播放完成
                while pygame.mixer.music.get_busy():
                    time.sleep(0.1)  # 每0.1秒检查一次
                
                print("✅ 音频播放完成")
                pygame.mixer.quit()
                
            except ImportError:
                print("ℹ️  安装pygame可以自动播放音频: pip install pygame")
            except Exception as e:
                print(f"⚠️  播放音频失败: {e}")

            return True
        else:
            print("❌ 接收到的音频数据为空")
            return False

    except requests.exceptions.Timeout:
        print("❌ 请求超时")
        return False
    except requests.exceptions.ConnectionError:
        print("❌ 连接失败，请确保TTS服务正在运行")
        return False
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False


def test_different_engines():
    """测试不同引擎"""
    engines = ["edgetts", "customTTS", "GSV", "openai"]

    print("\n🔄 测试不同TTS引擎...")

    for engine in engines:
        print(f"\n{'=' * 50}")
        print(f"🔧 测试引擎: {engine}")

        test_data = {
            "index": 1,
            "text": f"这是{engine}引擎的测试",
            "engine": engine,
            "voice": "default"
        }

        try:
            response = requests.post("http://localhost:8000/tts", json=test_data, timeout=10)

            if response.status_code == 200:
                print(f"✅ {engine} 引擎测试成功")
                # 保存音频文件
                output_file = f"test_{engine}.mp3"
                with open(output_file, 'wb') as f:
                    f.write(response.content)
                print(f"💾 音频已保存: {output_file}")
            else:
                print(f"❌ {engine} 引擎测试失败: {response.status_code}")
                print(f"错误信息: {response.text}")

        except Exception as e:
            print(f"❌ {engine} 引擎测试异常: {e}")


if __name__ == "__main__":
    print("🎯 TTS服务流式输出测试工具")
    print("=" * 60)

    # 测试1: 流式输出
    success = test_tts_streaming()

    if success:
        print("\n🎉 流式输出测试通过!")

        # 测试2: 不同引擎（可选）
        print("\n是否测试其他引擎？(y/n): ", end="")
        if input().lower() == 'y':
            test_different_engines()
    else:
        print("\n💥 流式输出测试失败!")
        sys.exit(1)

    print("\n✨ 测试完成!")
