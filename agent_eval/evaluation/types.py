
from typing import Any
from dataclasses import dataclass, field


@dataclass
class AgentResult:
    answer: str
    
    # agent 调用的工具列表, 以及每次调用的参数和返回值
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    
    # agent 执行的步骤数, 也就是 agent 执行的循环次数
    steps: int = 0
    
    # 是否发生错误
    error : str | None = None
    
    
"""
例子:
AgentResult(
    answer="结果是 56088",
    tool_calls=[
        {
            "name": "calculator",
            "arguments": {
                "expression": "123 * 456"
            }
        }
    ],
    steps=2
)
"""