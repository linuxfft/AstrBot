from astrbot import logger


class GoofishCallbackHandler(object):

    def __init__(self):
        self.logger = logger

    def pre_start(self):
        return

    async def process(self, message: str) -> bool:
        return False