import json

from openai import OpenAI




import inspect
from typing import Any, get_type_hints


PY2JSON = {str: "string", int: "integer", float: "number",
           bool: "boolean", list: "array", dict: "object"}

def to_openai_tool(fn):
    """
    Convert a Python function to an OpenAI tool format.
    """
    signature = inspect.signature(fn)
    hints = get_type_hints(fn)
    props,required = {}, []
    for name, param in signature.parameters.items():
        if name in hints:
            props[name] = {"type": PY2JSON.get(hints[name], "string")}
        else:
            props[name] = {"type": "string"}
        if param.default is param.empty:
            required.append(name)
    
    return {
        "type": "function",
        "function": {
            "name": fn.__name__,
            "description": inspect.getdoc(fn) or "",
            "parameters": {"type": "object", "properties": props, "required": required},
        },
    }
    
    
    
def execute_tool(tool_name : str, args : str, tools : dict) -> dict:
    if tool_name not in tools:
        raise ValueError(f"Tool {tool_name} not found.")
    try:
        # Convert args from JSON string to dictionary
        import json
        args_dict = json.loads(args)
        result = tools[tool_name](**args_dict)
        return {
            "success" : True,
            "result": result
        }
    except Exception as e:
        return {
            "success"   : False,
            "result": f"Error executing tool {tool_name}: {str(e)}"
        }

def Calculator(a: float, b: float, operation: str) -> float:
    """
    Perform a calculation based on the provided operation.
    * -> multiply
    / -> divide
    + -> add
    - -> subtract
    """
    if operation == "add":
        return a + b
    elif operation == "subtract":
        return a - b
    elif operation == "multiply":
        return a * b
    elif operation == "divide":
        if b != 0:
            return a / b
        else:
            raise ValueError("Cannot divide by zero.")
    else:
        raise ValueError(f"Unsupported operation: {operation}")

# Tool Registry
my_tools = {"Calculator": Calculator}


my_tools_openai = {name: to_openai_tool(fn) for name, fn in my_tools.items()} 

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

    tool_calls_name: list[dict[str, Any]] = []
    print("=== 逐步观察 Agent Loop ===")
    for turn in range(max_steps):
         # 理解loop,所以使用chat
        response = client.chat.completions.create(
            model=Model,
            messages=messages, # type: ignore
            tools=list(my_tools_openai.values()), # schema for tools # type: ignore
            #stream=True,
        )
        
        print(f"\n=== Response ===")
        print(response)
        
        message = response.choices[0].message
        tool_calls = message.tool_calls
        # 如果没有需要调用的工具，说明模型已经完成了任务，我们可以直接返回最终的输出。
        if not tool_calls:
            print("=== Final Model Output ===")
            return {"answer": message.content, "tool_calls": tool_calls_name, "steps": turn + 1}
        
        print(f"\n ============agent turn: {turn + 1} ==========")
        
        # 将模型的输出添加到消息列表中，以便在下一轮中作为上下文传递给模型。
        messages.append(message.model_dump(exclude_none=True))
        # 执行所有的需要调用的tool
        for call in tool_calls:
            print(f"\n--- tool call: {call.function.name} ---")
            tool_name = call.function.name
            
            tool_args = call.function.arguments
            tool_calls_name.append({
                "name": tool_name,
                "arguments": tool_args
            })
            
            result= execute_tool(tool_name, tool_args, my_tools)
            messages.append({
                "role" : "tool",
                "tool_call_id" : call.id,
                "content" : json.dumps(result, ensure_ascii=False)
            })
            
    raise RuntimeError(f"Agent loop exceeded max steps ({max_steps}). Last response: {message.content}") # type: ignore


