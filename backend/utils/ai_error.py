"""AI API 错误增强处理 — 检测 model_not_found / 404 并返回更明确的中文引导"""


def enhance_ai_error(e: Exception, model: str = "", base_url: str = "") -> str:
    """将 AI API 原始错误转为更明确的中文提示。

    特别处理 model_not_found (404)：百炼的 404 同时涵盖"模型不存在"和"没有访问权限"，
    需要引导用户检查模型名和权限。
    """
    err_msg = str(e)

    # 检测 model_not_found 错误（阿里云百炼 / OpenAI 兼容格式）
    is_model_not_found = (
        "model_not_found" in err_msg
        or ("does not exist" in err_msg and "model" in err_msg.lower())
        or ("404" in err_msg and "model" in err_msg.lower())
    )

    if is_model_not_found:
        # 提取模型名（百炼错误格式: The model `xxx` does not exist...）
        import re
        model_in_error = re.search(r"model\s+`([^`]+)`", err_msg)
        model_name = model_in_error.group(1) if model_in_error else (model or "未知模型")

        hint = (
            f"模型 `{model_name}` 不存在或您的 API Key 未开通该模型权限。\n"
            "请检查：\n"
            "1. 模型名是否正确（阿里云常用: qwen3.7-plus / qwen3.7-max / qwen-plus / qwen-max / qwen-turbo）\n"
            "2. 在百炼控制台确认已开通该模型的访问权限\n"
            "3. 如果使用旧域名 dashscope.aliyuncs.com 仍报错，请改用 WorkspaceId 版新域名\n"
            f"原始错误: {err_msg}"
        )
        return hint

    # 检测 401 / 403 权限错误
    if "401" in err_msg or "403" in err_msg or "Unauthorized" in err_msg or "Forbidden" in err_msg:
        return (
            f"API Key 无效或权限不足，请检查：\n"
            "1. Key 是否正确\n"
            "2. Key 是否有额度\n"
            "3. 左上角选择的 AI 提供商是否与 Key 匹配\n"
            f"原始错误: {err_msg}"
        )

    # 检测超时错误
    if "timeout" in err_msg.lower() or "timed out" in err_msg.lower():
        return f"AI 请求超时，请稍后重试（{err_msg}）"

    # 检测连接错误（openai SDK 的 APIConnectionError 通常 str(e) = "Connection error."）
    if err_msg.strip().lower() in ("connection error.", "connection error") or "apiconnectionerror" in err_msg.lower():
        return (
            f"无法连接到 AI 服务（{err_msg}）。请检查：\n"
            "1. API Key 是否有效（在提供商控制台验证）\n"
            "2. 左上角选择的 AI 提供商是否与 API Key 匹配\n"
            f"3. 当前 base_url: {base_url or '（未配置，将使用提供商默认）'}\n"
            "4. 网络是否能访问该 base_url（国内到境外服务可能需要代理）\n"
            "5. 如使用阿里云百炼，确认 API Key 属于对应地域（国内/国际）"
        )

    # 其他错误原样返回
    return err_msg
