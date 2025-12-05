import time
import threading
import io
import queue

class StreamingAudioPlayer:
    def __init__(self):
        self.audio_queue = queue.Queue()
        self.is_playing = False
        self.is_receiving = False
        self.total_bytes = 0
        self.chunk_count = 0
        self.playback_thread = None
        self.buffer = io.BytesIO()
        self.min_buffer_size = 2048  # 最小缓冲区大小（2KB）
        self.chunk_size = 1024  # 每块大小
        self.buffer_start_time = None

    def start_playback_thread(self):
        """启动播放线程"""

        def playback_worker():
            try:
                import pygame
                pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=4096)

                temp_buffer = io.BytesIO()
                bytes_played = 0

                print("🎵 播放线程启动")

                while self.is_playing or not self.audio_queue.empty():
                    try:
                        # 从队列获取音频数据（超时1秒）
                        chunk_data = self.audio_queue.get(timeout=1)

                        if chunk_data is None:  # 结束信号
                            break

                        # 写入临时缓冲区
                        # 记录缓冲区开始时间
                        if not self.buffer_start_time:
                            self.buffer_start_time = time.time()
                        temp_buffer.write(chunk_data)
                        bytes_played += len(chunk_data)

                        # 当积累足够数据时开始播放
                        if bytes_played >= self.min_buffer_size and not pygame.mixer.music.get_busy():
                            # # 等待0.5秒让缓冲区积累更多数据
                            # if self.is_receiving:
                            #     elapsed = time.time() - self.buffer_start_time
                            #     if elapsed < 0.5:
                            #         wait_time = 0.5 - elapsed
                            #         print(f"⏳ 等待 {wait_time:.2f} 秒让缓冲区积累数据...")
                            #         time.sleep(wait_time)

                            # 重置缓冲区位置
                            temp_buffer.seek(0)

                            # 加载并播放
                            pygame.mixer.music.load(temp_buffer)
                            pygame.mixer.music.play()

                            # 创建新的缓冲区用于下一段
                            temp_buffer = io.BytesIO()
                            bytes_played = 0

                        # 如果当前正在播放，等待完成
                        elif pygame.mixer.music.get_busy():
                            # 等待当前播放完成或缓冲区有足够数据
                            while pygame.mixer.music.get_busy() and self.audio_queue.qsize() < 5:
                                time.sleep(0.1)

                    except queue.Empty:
                        # 队列空但还在接收数据，继续等待
                        if self.is_receiving:
                            continue
                        else:
                            break

                # 播放剩余数据
                if temp_buffer.tell() > 0:
                    temp_buffer.seek(0)
                    pygame.mixer.music.load(temp_buffer)
                    pygame.mixer.music.play()

                    while pygame.mixer.music.get_busy():
                        time.sleep(0.1)

                pygame.mixer.quit()
                print("✅ 播放线程结束")

            except ImportError:
                print("❌ 未安装pygame")
            except Exception as e:
                print(f"❌ 播放线程错误: {e}")

        # 启动播放线程
        self.playback_thread = threading.Thread(target=playback_worker)
        self.playback_thread.daemon = True
        self.playback_thread.start()

    def add_audio_chunk(self, chunk_data):
        """添加音频数据块到队列"""
        self.audio_queue.put(chunk_data)
        self.total_bytes += len(chunk_data)
        self.chunk_count += 1

    def stop_receiving(self):
        """停止接收数据"""
        self.is_receiving = False

    def stop_playback(self):
        """停止播放"""
        self.is_playing = False
        # 发送结束信号
        self.audio_queue.put(None)

    def wait_for_completion(self):
        """等待播放完成"""
        if self.playback_thread:
            self.playback_thread.join(timeout=30)