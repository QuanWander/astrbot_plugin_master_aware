# 可移植性说明

## 核心（可迁移的概念）

- 主人识别：平台 + 用户 ID
- 记忆：关于主人的事实、称呼、相处模式
- 注入：把身份和记忆拼进对话上下文

## AstrBot 壳（不直接搬）

- `AstrMessageEvent`、`filter.on_llm_request`、`filter.on_decorating_result`
- `TextPart.mark_as_temp`
- AstrBot 页面注册、命令系统

## DSH 迁移

- 不照搬代码，按 DSH 的会话/身份模型重写
- 身份配置改为 `platform_accounts`：qq / dsh / hehe / web
- 旧的 `master_qq` 保留兼容

## 不迁移

- AstrBot 专属命令、页面、注入实现
