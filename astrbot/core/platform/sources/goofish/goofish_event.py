from astrbot.core.platform import AstrMessageEvent
from astrbot.core.platform.sources.goofish.goofish_live import GoofishClient


class GoofishMessageEvent(AstrMessageEvent):
    def __init__(
            self,
            message_str,
            message_obj,
            platform_meta,
            session_id,
            client: GoofishClient,
    ):
        super(GoofishMessageEvent, self).__init__(message_str, message_obj, platform_meta, session_id)
        self._client = client



