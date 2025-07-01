import asyncio
import re
from typing import Dict

from astrbot import logger
from astrbot.core.message.components import Plain
from astrbot.core.message.message_event_result import MessageChain
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
        self._client: GoofishClient = client

    @staticmethod
    async def _parse_text_blocks(
            message_chain: MessageChain):
        """解析成 块格式"""
        blocks = []
        text_content = ""

        for segment in message_chain.chain:
            if isinstance(segment, Plain):
                text_content += segment.text
            else:
                # 如果有文本内容，先添加文本块
                if text_content.strip():
                    blocks.append(
                        {
                            "type": "section",
                            "text": {"type": "mrkdwn", "text": text_content},
                        }
                    )
                    text_content = ""

        # 如果最后还有文本内容
        if text_content.strip():
            blocks.append(
                {"type": "section", "text": {"type": "mrkdwn", "text": text_content}}
            )

        return blocks, "" if blocks else text_content


    async def send(self, message: MessageChain):
        _, text = self._parse_text_blocks(message)
        logger.info(f"[Goofish] 机器人回复: {text}")
        # 添加机器人回复到上下文
        raw_message: Dict = self.message_obj.raw_message
        url_info = raw_message["1"]["10"]["reminderUrl"]
        item_id = url_info.split("itemId=")[1].split("&")[0] if "itemId=" in url_info else None
        self._client.context_manager.add_message_by_chat(self.message_obj.session_id,
                                                         self.message_obj.self_id, item_id,
                                                         "assistant", text)

        await self._client.send_msg(self._client.ws, self.message_obj.session_id, self.message_obj.sender.user_id, text)
        await super().send(message)


    async def send_streaming(self, generator, use_fallback: bool = False):
        if not use_fallback:
            buffer = None
            async for chain in generator:
                if not buffer:
                    buffer = chain
                else:
                    buffer.chain.extend(chain.chain)
            if not buffer:
                return
            buffer.squash_plain()
            await self.send(buffer)
            return await super().send_streaming(generator, use_fallback)

        buffer = ""
        pattern = re.compile(r"[^。？！~…]+[。？！~…]+")

        async for chain in generator:
            if isinstance(chain, MessageChain):
                for comp in chain.chain:
                    if isinstance(comp, Plain):
                        buffer += comp.text
                        if any(p in buffer for p in "。？！~…"):
                            buffer = await self.process_buffer(buffer, pattern)
                    else:
                        await self.send(MessageChain(chain=[comp]))
                        await asyncio.sleep(1.5)  # 限速

        if buffer.strip():
            await self.send(MessageChain([Plain(buffer)]))
        return await super().send_streaming(generator, use_fallback)



