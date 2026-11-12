from dataclasses import dataclass, field

@dataclass
class EvalCase:
    id : str
    input : str
    
    # 预期答案
    expected_answer_contains : list[str] = field(
        default_factory=list
        )
    
    # 预期工具调用顺序
    expected_tools: list[str] = field(
        default_factory=list
    )
    
    
EVAL_DATASET = [
    EvalCase(
        id="T1",
        input="1+2等于多少?",
        expected_answer_contains=["3"],
        expected_tools=["Calculator"]
    ),
     EvalCase(
        id="T2",
        input="计算 123 * 456",
        expected_answer_contains=["56088"],
        expected_tools=["calculator"]
    ),
     EvalCase(
        id="T3",
        input="计算 10 + 20，然后乘以 2",
        expected_answer_contains=["60"],
        expected_tools=[
            "calculator", # expected_tools 是有顺序的,帮助我们发现 Agent 是否遗漏工具调用，或者调用了错误的工具
            "calculator"
        ]
    ),
        
]