
from evaluation.dataset import EVAL_DATASET
from evaluation.runner import evaluate
from evaluation.types import AgentResult

from agent.my_agent import agent_loop as run_agent


def agent_adapter(user_input: str) -> AgentResult:

    # 调用你自己写的 Agent Loop
    raw_result = run_agent(user_input)

    print("=== Agent Loop Result ===")
    print(raw_result)
    # 将 Agent 的输出转换成统一格式
    return AgentResult(
        answer=raw_result["answer"],
        tool_calls=raw_result["tool_calls"],
        steps=raw_result["steps"],
        error=raw_result.get("error")
    )


if __name__ == "__main__":

    report = evaluate(
        agent=agent_adapter,
        dataset=EVAL_DATASET
    )

    print("\nEvaluation Report")
    print("=================")

    for key, value in report["metrics"].items():
        print(f"{key}: {value}")
