from langchain.agents import create_agent
from langchain.messages import SystemMessage
import main as base



agent = create_agent(
    model=base.llm,                             # 直接用 base 里的 llm
    tools=[base.get_weather, base.buy_coat],    # 直接用 base 里的 tool
    system_prompt=(
        "You are a helpful assistant that can provide weather information "
        "and assist with purchasing items. "
        "If the weather is cold, you MUST call buy_coat."
    ),
)

human_prompt = "What is the weather in New York City? If it's cold, please buy me a coat."

# result = agent.invoke(
#     {"messages": [{"role": "user", "content": human_prompt}]}
# )

print("=== 逐步观察 Agent Loop ===")
for step in agent.stream(
    {"messages": [{"role": "user", "content": human_prompt}]},
    stream_mode="updates",
):
    for node_name, update in step.items():
        print(f"\n--- node: {node_name} ---")
        for msg in update.get("messages", []):
            msg.pretty_print()

