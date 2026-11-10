import json

from langchain.agents import create_agent
from openai import OpenAI

import main as base
import my_untils 

# Tool Registry
my_tools = {"get_weather": base.get_weather, "buy_coat": base.buy_coat}


my_tools_openai = {name: my_untils.to_openai_tool(fn) for name, fn in my_tools.items()} 

print("=== my_tools_openai ===")
for name, tool in my_tools_openai.items():
    print(f"\n--- tool: {name} ---")
    print(tool)


client = OpenAI(api_key="EMPTY", base_url="http://localhost:3425/v1")
Model = "workbuddy-ai/hy4free"

SYSTEM_PROMPT = (
    "You are a helpful assistant. Use the provided tools when needed. "
)



def agent_loop(human_prompt: str, max_steps: int = 10):
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": human_prompt},
    ]

    print("=== 逐步观察 Agent Loop ===")
    for turn in range(max_steps):
         # 理解loop,所以使用chat
        response = client.chat.completions.create(
            model=Model,
            messages=messages,
            tools=list(my_tools_openai.values()), # schema for tools
            #stream=True,
        )
        
        print(f"\n=== Response ===")
        print(response)
        
        message = response.choices[0].message
        tool_calls = message.tool_calls
        # 如果没有需要调用的工具，说明模型已经完成了任务，我们可以直接返回最终的输出。
        if not tool_calls:
            print("=== Final Model Output ===")
            return message.content
        
        print(f"\n ============agent turn: {turn + 1} ==========")
        
        # 将模型的输出添加到消息列表中，以便在下一轮中作为上下文传递给模型。
        messages.append(message.model_dump(exclude_none=True))
        # 执行所有的需要调用的tool
        for call in tool_calls:
            print(f"\n--- tool call: {call.function.name} ---")
            tool_name = call.function.name
            tool_args = call.function.arguments
            
            result= my_untils.execute_tool(tool_name, tool_args, my_tools)
            messages.append({
                "role" : "tool",
                "tool_call_id" : call.id,
                "content" : json.dumps(result, ensure_ascii=False)
            })
            
    raise RuntimeError(f"Agent loop exceeded max steps ({max_steps}). Last response: {message.content}")


result =  agent_loop("What is the weather in New York City? If it's cold, please buy me a coat.")

print(result)
