from tools.motion_drive.momask_bvh_vrma_flow import from_text_to_vrma
from src.infrastructure.logging.logger import get_logger

logger = get_logger()


class VRMAHandler:
    def __init__(self):
        self.name = "VRMA"

    @staticmethod
    async def generate_vrma(text: str) -> str:
        vrma_file_path = await from_text_to_vrma(text)
        return vrma_file_path

    @staticmethod
    async def handle_vrma_direct_play(motion_text: str = None, valid_vrma_path: str = None):
        if motion_text is None and valid_vrma_path is not None:
            play_select_vrma(valid_vrma_path)
            return

        gen_vrma_file_path = await from_text_to_vrma(motion_text)
        play_select_vrma(gen_vrma_file_path)


# Not implemented yet
def play_select_vrma(path: str):
    logger.warning("Not implemented yet")
