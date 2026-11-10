
import inspect
from typing import get_type_hints


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