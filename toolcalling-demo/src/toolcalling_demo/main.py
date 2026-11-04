import tomllib
from pathlib import Path

from langchain.messages import HumanMessage, ToolMessage
from langchain.tools import tool
from langchain_deepseek import ChatDeepSeek
from pydantic import Field

# 配置文件路径
cfg = tomllib.loads((Path(__file__).parent.parent.parent / "config.toml").read_text(encoding="utf-8"))
llm = ChatDeepSeek(model=cfg["model"], api_key=cfg["api_key"], base_url=cfg["base_url"])



@tool
def calculate_shipping_cost(
    weight_kg : float = Field(description="包裹的重量，单位为千克"),
    destination : str = Field(description="目的地，例如：北京，上海，广州"),
    is_express : bool = Field(description="是否加急配送")
) -> str:
    """计算给定重量和目的地的快递的费用"""
    # 模拟业务逻辑计算运费
    base_rate = 10.0
    rate_per_kg = 5.0
    cost = base_rate + weight_kg * rate_per_kg
    if is_express:
        cost *= 1.5
    return f"运费计算结果：{cost:.2f} 元（目的地：{destination}，重量：{weight_kg}kg，加急：{is_express}）"



llm_with_tools = llm.bind_tools([calculate_shipping_cost])


query = HumanMessage("帮我计算一下邮寄5kg重量的衣服最快的速度到北京需要多少钱？")

response = llm_with_tools.invoke([query])

print("模型请求调用:", response.tool_calls)

# 3. 拦截并手动执行工具
messages = [query, response]  # 保留对话上下文

for tool_call in response.tool_calls:
    if tool_call["name"] == "calculate_shipping_cost":
        # 获取模型传过来的参数
        args = tool_call["args"]
        # 在本地执行真正的 Python 函数
        tool_result = calculate_shipping_cost.invoke(args)
        
        # 4. 构造 ToolMessage 关联调用 ID，并加入消息历史
        messages.append(
            ToolMessage(
                content=str(tool_result), 
                tool_call_id=tool_call["id"] # 必须与请求的 id 严格对应
            )
        )

# 5. 再次将带有工具执行结果的消息发给模型，获取最终答案
final_response = llm_with_tools.invoke(messages)
print("最终回答:", final_response.content)
    