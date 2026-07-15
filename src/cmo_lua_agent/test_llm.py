"""
最小 LLM 连通性测试。

用于验证：
1. .env 是否被正确读取；
2. API Key、Base URL 和模型名称是否正确；
3. Anthropic 客户端是否能成功调用模型；
4. 模型返回内容能否被正常解析和打印。
"""

from __future__ import annotations

from anthropic import APIConnectionError
from anthropic import APIStatusError
from anthropic import AuthenticationError


from cmo_lua_agent.llm_config import load_config
from cmo_lua_agent.llm.client import ClaudeClient

def main() -> int:
    try:
        config = load_config()
        client = ClaudeClient(config.llm)

        print("正在测试 LLM 连接……")
        print(f"模型：{config.llm.model_id}")
        print(f"Base URL：{config.llm.base_url or 'Anthropic 默认地址'}")

        response = client.create_message(
            system="你是一个简洁、准确的测试助手。",
            messages=[
                {
                    "role": "user",
                    "content": (
                        "请回复一句话，说明 LLM 连接测试成功，"
                        "并计算 17 + 25。"
                    ),
                }
            ],
            max_tokens=200,
        )

        texts: list[str] = []

        for block in response.content:
            if getattr(block, "type", None) == "text":
                texts.append(block.text)

        if not texts:
            print("调用成功，但模型没有返回文本内容。")
            print(f"stop_reason：{response.stop_reason}")
            return 1

        print("\n模型回答：")
        print("\n".join(texts))

        print("\n调用信息：")
        print(f"stop_reason：{response.stop_reason}")

        if getattr(response, "usage", None):
            print(f"输入 Token：{response.usage.input_tokens}")
            print(f"输出 Token：{response.usage.output_tokens}")

        print("\nLLM 连接测试成功。")
        return 0

    except AuthenticationError as exc:
        print("认证失败：请检查 ANTHROPIC_API_KEY。")
        print(exc)
        return 2

    except APIConnectionError as exc:
        print("连接失败：请检查网络、代理或 ANTHROPIC_BASE_URL。")
        print(exc)
        return 3

    except APIStatusError as exc:
        print(f"API 返回错误，HTTP 状态码：{exc.status_code}")
        print(exc)
        return 4

    except KeyError as exc:
        print(f"缺少配置项：{exc}")
        return 5

    except Exception as exc:
        print(f"测试失败：{type(exc).__name__}: {exc}")
        return 10


if __name__ == "__main__":
    raise SystemExit(main())