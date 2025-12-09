from tools.motion_drive.momask_bvh_vrma_flow import from_text_to_vrma


class VRMAHandler:
    def __init__(self):
        self.name = "VRMA"

    @staticmethod
    async def generate_vrma(text: str) -> str:
         vrma_file_path = await from_text_to_vrma(text)
         return vrma_file_path
