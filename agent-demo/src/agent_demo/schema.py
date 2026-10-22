from typing import Literal

from pydantic import BaseModel, Field


class ResponseModel(BaseModel):
    category : Literal["网络问题","账号问题","功能问题","其他"] = Field(description="问题类型")
    priority : Literal["low", "medium", "high"] = Field(description="优先级")
    summary : str = Field(description="一句话摘要")
    suggested_action : str = Field(description="建议处理动作")
