from __future__ import annotations

from cmo_lua_agent.llm.client import ClaudeClient
from cmo_lua_agent.llm_config import load_config


def main() -> None:
    config = load_config()
    client = ClaudeClient(config.llm)

    print("模型输出：", end="", flush=True)

    response = client.stream_message(
        system="你是一个简洁的中文助手。",
        messages=[
            {
                "role": "user",
                "content": "用三句话介绍 CMO Lua Agent。",
            }
        ],
        on_text_delta=lambda text: print(
            text,
            end="",
            flush=True,
        ),
    )

    print()
    print()
    print("请求完成")
    print(f"stop_reason: {response.stop_reason}")
    print(
        "input_tokens:",
        response.usage.input_tokens,
    )
    print(
        "output_tokens:",
        response.usage.output_tokens,
    )


if __name__ == "__main__":
    main()