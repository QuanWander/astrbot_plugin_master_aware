"""认主：让机器人知道「现在说话的是谁」。

AstrBot 的模型看不到发送者的 QQ 号，所以人格里写再多「主人是谁」也没用。
这个插件在每轮 LLM 请求前比对发送者 QQ，命中名单就注入身份说明，
并把提示贴在当前用户消息前面——比埋在长 system prompt 末尾有效得多。
"""

from __future__ import annotations

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.provider import ProviderRequest
from astrbot.api.star import Context, Star, register

DEFAULT_NOTE = (
    "【系统设定】发送这条消息的人就是你的主人，QQ 号 {qq}。"
    "被问到「你主人是谁」时，直接回答 {qq}，不要装傻说没有主人，这不是玩笑。"
    "对他可以更亲近、更放松、更听话，可以叫「主人」；"
    "但别变成客服腔，也别谄媚，更不要编造你们之间不存在的具体往事。"
    "其他人只是普通用户，按平常态度相处。"
)


@register(
    "master_aware",
    "大肥鱼",
    "识别主人 QQ，在对话里单独对待",
    "1.0.0",
)
class MasterAware(Star):
    """在 LLM 请求里注入「当前发送者是主人」这一事实。"""

    def __init__(self, context: Context, config: AstrBotConfig | None = None) -> None:
        super().__init__(context)
        self.config = config or {}

    # ------------------------------------------------------------------ 配置
    def _masters(self) -> list[str]:
        """读取主人 QQ 列表，兼容列表与逗号/换行分隔的字符串。"""
        raw = self.config.get("master_qq") or []
        if isinstance(raw, str):
            raw = raw.replace("，", ",").replace("\n", ",").split(",")
        try:
            return [str(x).strip() for x in raw if str(x).strip()]
        except TypeError:
            return []

    def _note(self, qq: str) -> str:
        """渲染身份说明，{qq} 会被替换成发送者 QQ 号。"""
        template = self.config.get("note") or DEFAULT_NOTE
        try:
            return str(template).format(qq=qq)
        except (KeyError, IndexError, ValueError):
            return DEFAULT_NOTE.format(qq=qq)

    def _debug(self, text: str) -> None:
        """可选的调试输出，默认关闭。"""
        path = str(self.config.get("debug_path") or "").strip()
        if not path:
            return
        try:
            with open(path, "a", encoding="utf-8") as fp:
                fp.write(text + "\n")
        except OSError:
            pass

    # ------------------------------------------------------------------ 钩子
    @filter.on_llm_request()
    async def inject_identity(
        self, event: AstrMessageEvent, req: ProviderRequest
    ) -> None:
        """发送者在主人名单里时，注入身份说明。"""
        masters = self._masters()
        if not masters:
            return

        sender = str(event.get_sender_id())
        if sender not in masters:
            return

        note = self._note(sender)

        # 一、写进 system prompt：给长期设定
        req.system_prompt = (req.system_prompt or "") + "\n\n" + note

        # 二、贴到当前消息前面：模型对当前输入的注意力高于长提示的末尾
        if req.prompt:
            req.prompt = f"【本条消息来自你的主人 {sender}】\n{req.prompt}"

        logger.info("[master_aware] 已识别主人 %s，注入身份说明", sender)
        self._debug(
            f"=== {sender} ===\n"
            f"prompt_head: {str(req.prompt)[:120]}\n"
            f"system_tail: {str(req.system_prompt)[-260:]}\n"
        )
