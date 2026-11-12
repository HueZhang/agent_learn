
import json
import time

from dataclasses import asdict
from pathlib import Path
from typing import Callable

from evaluation.dataset import EvalCase
from evaluation.types import AgentResult


def evaluate(
    agent: Callable[[str], AgentResult], # agent 是一个函数, 接收一个字符串输入, 返回一个 AgentResult 对象
    dataset: list[EvalCase],
    report_path: str = "reports/report.json"
):
    results = []

    for case in dataset:
        start = time.perf_counter()

        try:
            result = agent(case.input)

        except Exception as e:
            result = AgentResult(
                answer="",
                error=str(e)
            )

        # 计算延迟
        latency = time.perf_counter() - start

        # 1. 检查最终答案
        answer_match = all(
            expected.lower() in result.answer.lower() 
            for expected in case.expected_answer_contains
        )

        # 2. 检查工具选择和调用顺序
        actual_tools = [
            call["name"]
            for call in result.tool_calls
        ]

        tool_match = actual_tools == case.expected_tools

        # 3. 判断任务是否成功
        success = (
            answer_match
            and tool_match
            and result.error is None
        )

        results.append({
            "id": case.id,
            "input": case.input,
            "success": success,
            "answer_match": answer_match,
            "tool_match": tool_match,
            "expected_tools": case.expected_tools,
            "actual_tools": actual_tools,
            "answer": result.answer,
            "steps": result.steps,
            "latency": round(latency, 3),
            "error": result.error
        })

    # 4. 统计指标
    total = len(results)

    metrics = {
        "total": total,
        "success_rate": (
            sum(r["success"] for r in results) / total
            if total else 0
        ),
        "tool_selection_accuracy": (
            sum(r["tool_match"] for r in results) / total
            if total else 0
        ),
        "error_rate": (
            sum(r["error"] is not None for r in results) / total
            if total else 0
        ),
        "avg_steps": (
            sum(r["steps"] for r in results) / total
            if total else 0
        ),
        "avg_latency": (
            sum(r["latency"] for r in results) / total
            if total else 0
        )
    }

    # 5. 保存报告
    report = {
        "metrics": metrics,
        "results": results
    }

    path = Path(report_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        json.dump(
            report,
            f,
            ensure_ascii=False,
            indent=2
        )

    return report
