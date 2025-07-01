import asyncio

import threading
import uuid
from typing import Dict

from .goofish_event import GoofishMessageEvent
from .goofish_handlers import GoofishCallbackHandler
from .goofish_live import GoofishClient, GoodfishMsgTopic
from ...register import register_platform_adapter
from astrbot import logger

from astrbot.api.platform import (
    Platform,
    AstrBotMessage,
    MessageMember,
    MessageType,
    PlatformMetadata,
)


@register_platform_adapter("goofish", "咸鱼机器人API适配器")
class GoofishPlatformAdapter(Platform):
    def __init__(
            self, platform_config: dict, platform_settings: dict, event_queue: asyncio.Queue
    ) -> None:
        super().__init__(event_queue)

        self._shutdown_event: threading.Event | None = None

        self.config = platform_config

        self._client = GoofishClient(platform_config, platform_settings)

        class AstrCallbackClient(GoofishCallbackHandler):
            async def process(self_, message: Dict) -> bool:
                abm = await self.convert_msg(message)
                await self.handle_msg(abm)

                return True

        self.client = AstrCallbackClient()

        self._client.register_callback_handler(GoodfishMsgTopic.Order, self.client)

    def meta(self) -> PlatformMetadata:
        return PlatformMetadata(
            name="goofish",
            description="咸鱼机器人API适配器",
            id=self.config.get("id"),
        )


    async def convert_msg(
        self, message: Dict
    ) -> AstrBotMessage:
        create_time = int(message["1"]["5"])
        send_user_name = message["1"]["10"]["reminderTitle"]
        send_user_id = message["1"]["10"]["senderUserId"]
        send_message = message["1"]["10"]["reminderContent"]
        chat_id = message["1"]["2"].split('@')[0]
        abm = AstrBotMessage()
        abm.message = []
        abm.message_str = send_message
        abm.timestamp = create_time
        abm.type = MessageType.FRIEND_MESSAGE
        abm.sender = MessageMember(
            user_id=send_user_id, nickname=send_user_name
        )
        abm.self_id = self._client.myid
        abm.message_id = uuid.uuid4().hex
        abm.raw_message = message

        abm.session_id = chat_id

        message_type: str = "text" # 只有文本形式
        match message_type:
            case "text":
                abm.message.append(send_message)
            case "audio":
                pass

        return abm  # 别忘了返回转换后的消息对象


    async def handle_msg(self, abm: AstrBotMessage):
        event = GoofishMessageEvent(
            message_str=abm.message_str,
            message_obj=abm,
            platform_meta=self.meta(),
            session_id=abm.session_id,
            client=self._client,
        )

        self._event_queue.put_nowait(event)

    def get_client(self):
        return self.client

    async def run(self):
        # await self.client_.start()
        # 钉钉的 SDK 并没有实现真正的异步，start() 里面有堵塞方法。
        def start_client(async_loop: asyncio.AbstractEventLoop):
            try:
                if not self._shutdown_event:
                    self._shutdown_event = threading.Event()
                task = async_loop.create_task(self._client.main_task())
                self._shutdown_event.wait()
                if task.done():
                    task.result()
                self._shutdown_event.clear()
                self._shutdown_event = None
            except Exception as e:
                if "Graceful shutdown" in str(e):
                    logger.info("[Goofish] 闲鱼适配器已被优雅地关闭")
                    return
                logger.error(f"[Goofish] 闲鱼机器人启动失败: {e}")

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, start_client, loop)

    async def terminate(self):
        await self._client.close_main_task()
        if self._shutdown_event:
            self._shutdown_event.set()
