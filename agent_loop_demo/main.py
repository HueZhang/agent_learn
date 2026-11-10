# 从本机 3425 端口获取 deepseek-flash 模型
from langchain_deepseek import ChatDeepSeek
from langchain.tools import tool

llm = ChatDeepSeek(model="workbuddy-ai/hy4free", api_key="EMPTY", base_url="http://localhost:3425/v1")



# @tool
def get_weather(city: str) -> str:
    """Get the weather for a given city."""
    return f"The weather in {city} is very cold."

# @tool
def buy_coat() -> str:
    """购买一件大衣"""
    return "您已成功购买一件大衣。"

