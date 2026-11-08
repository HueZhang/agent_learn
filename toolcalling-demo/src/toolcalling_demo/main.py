from langchain.messages import HumanMessage, SystemMessage, ToolMessage
from langchain.tools import tool
from langchain_deepseek import ChatDeepSeek
from pydantic import Field

# 从本机 3425 端口获取 deepseek-flash 模型
llm = ChatDeepSeek(model="workbuddy-ai/hy4free", api_key="EMPTY", base_url="http://localhost:3425/v1")



@tool
def calculate_shipping_cost(
    weight_kg : float = Field(description="包裹的重量，单位为千克"),
    destination : str = Field(description="目的地，例如：北京，上海，广州"),
    is_express : bool = Field(description="是否加急配送")
) -> str:
    """计算给定重量和目的地的快递的费用
        
         Args:
        weight_kg: 包裹的重量，单位为千克
        destination: 目的地，例如：北京，上海，广州
        is_express: 是否加急配送
    """
    # 模拟业务逻辑计算运费
    base_rate = 10.0
    rate_per_kg = 5.0
    cost = base_rate + weight_kg * rate_per_kg
    if is_express:
        cost *= 1.5
    return f"运费计算结果：{cost:.2f} 元（目的地：{destination}，重量：{weight_kg}kg，加急：{is_express}）"



@tool
def get_weather(city: str = Field(description="城市名称，例如：北京，上海，广州")) -> str:
    """获取指定城市的天气信息"""
    # 模拟获取天气信息
    return f"{city}的天气是晴天，温度25°C。"

llm_with_tools = llm.bind_tools([calculate_shipping_cost, get_weather])


tools_by_name = {
    "calculate_shipping_cost": calculate_shipping_cost,
    "get_weather": get_weather,
}


query = HumanMessage("帮我计算一下邮寄5kg重量的衣服最快的速度到北京需要多少钱, 并且顺便告诉我北京的天气情况。")

format_instruction = SystemMessage(content="回答结果在合适的地方可以加上一些emoji表情符号，增加趣味性。")

response = llm_with_tools.invoke([query])

print("模型请求调用:", response.tool_calls)

# 3. 拦截并手动执行工具
messages = [format_instruction, query, response]  # 保留对话上下文

for tool_call in response.tool_calls:
    tool = tools_by_name.get(tool_call["name"])
    if tool:
        # 执行工具
        tool_result = tool.invoke(tool_call["args"])
        # 将工具执行结果封装为 ToolMessage 并添加到消息列表中
        messages.append(ToolMessage(content=tool_result, tool_name=tool_call["name"], tool_call_id=tool_call["id"]))
    else:
        print(f"未找到工具: {tool_call['name']}")
# 5. 再次将带有工具执行结果的消息发给模型，获取最终答案
final_response = llm_with_tools.invoke(messages)
print("最终回答:", final_response.content)
    