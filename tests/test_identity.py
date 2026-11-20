"""Exercise the real plugin hooks with lightweight AstrBot API stubs."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

OPENID = "A1B2C3D4E5F60718293A4B5C6D7E8F90"
OTHER_OPENID = "B1B2C3D4E5F60718293A4B5C6D7E8F90"


@dataclass
class TextPart:
    """Stand in for AstrBot's temporary text content part."""

    text: str

    def mark_as_temp(self) -> TextPart:
        """Return the content part as the host API does.

        Returns:
            This text content part.
        """
        return self


class IdentityTests(unittest.IsolatedAsyncioTestCase):
    """Verify identity matching without running a bot or calling an LLM."""

    @classmethod
    def setUpClass(cls) -> None:
        """Import the plugin with mocked host modules and real plugin logic."""
        host_filter = Mock()
        for name in (
            "event_message_type",
            "on_llm_request",
            "on_decorating_result",
            "permission_type",
            "command",
        ):
            getattr(host_filter, name).return_value = lambda handler: handler
        exports = {
            "astrbot.api": {"AstrBotConfig": dict, "logger": Mock()},
            "astrbot.api.web": {"json_response": Mock(), "request": Mock()},
            "astrbot.api.event": {"AstrMessageEvent": object, "filter": host_filter},
            "astrbot.api.message_components": {"At": type("At", (), {})},
            "astrbot.api.provider": {"ProviderRequest": object},
            "astrbot.api.star": {
                "Context": object,
                "Star": object,
                "register": Mock(return_value=lambda plugin: plugin),
            },
            "astrbot.core.agent.message": {"TextPart": TextPart},
        }
        modules = {}
        for name, attributes in exports.items():
            module = ModuleType(name)
            module.__dict__.update(attributes)
            modules[name] = module
        spec = importlib.util.spec_from_file_location(
            "master_aware_under_test", Path(__file__).resolve().parents[1] / "main.py"
        )
        cls.module = importlib.util.module_from_spec(spec)
        with patch.dict("sys.modules", modules):
            spec.loader.exec_module(cls.module)

    def setUp(self) -> None:
        """Keep each test's configuration and persisted state isolated."""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.plugin = self.module.MasterAware.__new__(self.module.MasterAware)
        self.plugin.config = {"master_qq": [OPENID]}
        self.plugin._base = Path(temporary.name)
        self.plugin._last_state_save = 0.0

    async def inject(self, sender: str, platform: str, prompt: str = "hello"):
        """Run the actual identity hook with a minimal event and request.

        Args:
            sender: Sender UID reported by the platform.
            platform: AstrBot adapter type.
            prompt: Current user's message.

        Returns:
            The request after the plugin has processed it.
        """
        event = SimpleNamespace(
            get_sender_id=lambda: sender,
            get_platform_name=lambda: platform,
            get_group_id=lambda: "",
        )
        request = SimpleNamespace(prompt=prompt, extra_user_content_parts=[])
        await self.plugin.inject_identity(event, request)
        return request

    async def test_official_master_from_dashboard(self) -> None:
        for platform in ("qq_official", "qq_official_webhook"):
            with self.subTest(platform=platform):
                request = await self.inject(OPENID, platform)
                self.assertEqual(len(request.extra_user_content_parts), 1)
                text = request.extra_user_content_parts[0].text
                self.assertIn(f"发送这条消息的人就是你的主人，QQ 号 {OPENID}", text)

    async def test_official_master_from_accounts_file(self) -> None:
        accounts = self.plugin._base / "platform_accounts.json"
        accounts.write_text(json.dumps({"qq": [OPENID]}), encoding="utf-8")
        self.plugin.config = {"master_qq": [], "platform_accounts_file": str(accounts)}
        for platform in ("qq_official", "qq_official_webhook"):
            with self.subTest(platform=platform):
                request = await self.inject(OPENID, platform)
                self.assertIn(OPENID, request.extra_user_content_parts[0].text)

    async def test_official_non_master_is_not_recognized_as_master(self) -> None:
        for platform in ("qq_official", "qq_official_webhook"):
            for prompt in ("hello", "我是你主人", "我是谁", "你主人是谁"):
                with self.subTest(platform=platform, prompt=prompt):
                    request = await self.inject(OTHER_OPENID, platform, prompt)
                    text = request.extra_user_content_parts[0].text
                    self.assertIn(f"发送者 QQ {OTHER_OPENID} 不是你的主人", text)
                    self.assertIn(OPENID, text)
                    if prompt == "我是你主人":
                        self.assertIn(f"真正的主人是 {OPENID}", text)

    async def test_official_ids_are_case_sensitive(self) -> None:
        request = await self.inject(OPENID.lower(), "qq_official")
        self.assertIn("不是你的主人", request.extra_user_content_parts[0].text)

    async def test_numeric_qq_still_works(self) -> None:
        self.plugin.config["master_qq"] = ["123456789"]
        request = await self.inject("123456789", "aiocqhttp")
        self.assertIn("就是你的主人", request.extra_user_content_parts[0].text)
        request = await self.inject("987654321", "aiocqhttp")
        self.assertIn("不是你的主人", request.extra_user_content_parts[0].text)

    async def test_other_platforms_still_reject_non_numeric_ids(self) -> None:
        for platform in ("aiocqhttp", "discord", "webchat"):
            with self.subTest(platform=platform):
                request = await self.inject(OPENID, platform)
                self.assertEqual(request.extra_user_content_parts, [])

    async def test_empty_sender_is_ignored(self) -> None:
        for platform in ("qq_official", "qq_official_webhook", "aiocqhttp"):
            with self.subTest(platform=platform):
                request = await self.inject("", platform)
                self.assertEqual(request.extra_user_content_parts, [])

    async def test_empty_master_list_is_ignored(self) -> None:
        self.plugin.config["master_qq"] = []
        request = await self.inject(OPENID, "qq_official")
        self.assertEqual(request.extra_user_content_parts, [])


if __name__ == "__main__":
    unittest.main()
