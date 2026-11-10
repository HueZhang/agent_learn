1. 模型会出错，有幻觉；需要有兜底设计
2. 上下文窗口，token，成本，延迟

！ 重点：
评测（eval）：怎么判断 agent 变好还是变差，这是目前最缺人的环节之一
可观测性：日志、trace、成本监控
稳定性：超时、限流、幂等、权限控制、安全（比如提示词注入）
异步任务、状态持久化、与现有业务系统集成

判断什么该交给模型，什么该留给代码
路径取决于输入内容，无法穷举 → 才需要 agent。

RAG：

1. 为什么选择 RAG 方法
2. RAG 处理流程（The RAG pipeline）
3. 索引处理：数据分块、基于上下文的检索方式（Indexing: chunking, contextual retrieval）
4. 检索方式：BM25、DPR、ColBERT（Retrieval: BM25, DPR, ColBERT）
5. 代理式 RAG：自我 RAG、搜索-R1 （Agentic RAG: Self-RAG, Search-R1）
6. 失效模式分析 （Failure modes）

bind_tools：

```
model_with_tools = model.bind_tools([GetWeather, GetPrice])
```

单个 Agent 绑定的工具数量建议控制在 5–10 个 以内。如果工具过多，应使用动态选择策略，而不是一次性全部绑定，因为过多的工具描述会稀释模型的注意力，影响选择准确性。

bind_tools 内部会做两件事：
第一步：解析工具定义。
第二步：将工具信息"绑定"到模型对象上.

bind_tools 返回的 llm_with_tools 是一个"记住了有哪些工具可用"的模型包装器。
当 LLM 收到你的 query（"邮寄5kg到北京最快多少钱"）以及 bind_tools 附带的工具 schema 后，它会根据问题与工具描述的匹配程度，自行判断是否需要调用工具。如果判断需要，模型会在响应中生成 tool_calls 字段，指明要调用哪个工具以及传入什么参数。

1.  如何动态选择工具?

    根据当前用户query，先从工具库中筛选出最相关的Top-K个工具，再只把这些工具绑定给模型.
    主流实现有几种：
    1. 基于向量检索的中间件，使用langchain-dynamic-tools-middleware这类中间件

    ```python
    from langchain_dynamic_tools import DynamicToolSelectorMiddleware

     tool_router = DynamicToolSelectorMiddleware(tools=all_tools, top_k=4)

    ```

    2. LLM路由（RouterChain）

       用一个轻量级LLM专门做工具选择：先让router LLM根据query判断需要哪些工具，再用选中的工具调用主模型。缺点是每步多一次LLM调用，增加延迟和成本。

    3. LangGraph状态机动态切换

       在LangGraph中，根据当前对话状态，用条件边动态改变bind_tools的工具列表。例如不同步骤对应不同的工具配置，状态机在“步骤”间切换时，工具集也随之变化

    4. `create_agent`自动选择

       传入所有tool，但是tool过多不合适.

2.  模型理解tool的功能是通过docstring吗？ 没有写docstring呢？

    自动提取其函数签名、类型注解和 docstring，将其转换为模型能理解的 JSON Schema。

    没有docstring,只能根据类型注解（如str、float）猜测语义，准确性会明显下降.

    替代方案：如果确实不方便写docstring，可以在@tool中显式传入description和args_schema（Pydantic模型，每个字段用Field(description=...)标注），手动提供完整的Schema信息。但最佳实践仍然是写好docstring，因为它是模型理解工具意图的最直接来源。

3.  tool的定义方式有哪些？

    @tool装饰器（最常用）,StructuredTool.from_function,Tool.from_function,继承BaseTool, 直接定义Pydantic模型作为工具

4.  为什么`llm_with_tools.invoke([query])` 这样传入问题?

    invoke方法的输入是一个消息列表，这是LangChain聊天模型的标准接口约定。消息列表中可以包含多种角色：

         HumanMessage：用户输入
    
         SystemMessage：系统指令
    
         AIMessage：模型之前的回复（包括tool_calls）
    
         ToolMessage：工具执行结果

5.  工具执行是在本地的.

    执行方式:
    1. 手动执行

    ```python
       from langchain_core.messages import HumanMessage, ToolMessage
    
       ai_message = response # 这是 AIMessage，包含 tool_calls
    
       tools_by_name = {"calculate_shipping_cost": calculate_shipping_cost}
    
       tool_messages = []
       for tool_call in ai_message.tool_calls: # 1. 根据名字找到对应的工具
       selected_tool = tools_by_name[tool_call["name"]] # 2. 执行工具，传入参数
       observation = selected_tool.invoke(tool_call["args"]) # 3. 包装成 ToolMessage，必须带上 tool_call_id 用于和 AIMessage 匹配
       tool_messages.append(
       ToolMessage(content=str(observation), tool_call_id=tool_call["id"])
       )
    
       messages = [query, ai_message] + tool_messages
       final_response = llm_with_tools.invoke(messages)
       print(final_response.content) # 模型基于工具结果生成的最终回答
    ```

    2.  通过`ToolNode`自动执行

    ```python
       from langgraph.prebuilt import ToolNode
    
       tool_node = ToolNode([calculate_shipping_cost])
    
    ```



# Message:

如何告诉ai.

```python
# 1. 纯字符串（最简单，会被当成一条 HumanMessage）
model.invoke("你好")

# 2. 字典（OpenAI 风格，就是你贴的那种）
model.invoke([
    {"role": "system", "content": "你是助手"},
    {"role": "user", "content": "你好"},
])

# 3. Message 对象
from langchain.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
# 旧版导入路径：from langchain_core.messages import ...
model.invoke([
    SystemMessage("你是助手"),
    HumanMessage("你好"),
])

# 4. 元组简写（较老的写法，多见于旧示例）
model.invoke([("system", "你是助手"), ("human", "你好")])

# 5. 提示词模板（带变量，可复用）
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
prompt = ChatPromptTemplate.from_messages([
    ("system", "你是{role}"),
    MessagesPlaceholder("history"),   # 插入一整段历史消息
    ("human", "{question}"),
])
chain = prompt | model
```

**1、2、4 最终都会被转换成 Message 对象**，所以功能上基本等价

## role:

| role（字典） | 对应的 Message 类 | 谁产生   | 用途                          |
| ------------ | ----------------- | -------- | ----------------------------- |
| `system`     | `SystemMessage`   | 开发者   | 设定模型的身份、规则、风格    |
| `user`       | `HumanMessage`    | 用户     | 用户的输入                    |
| `assistant`  | `AIMessage`       | 模型     | 模型的回复，可带 `tool_calls` |
| `tool`       | `ToolMessage`     | 你的代码 | 工具执行结果，回传给模型      |

注意:不同模型对 `system` 的位置有要求。大多数要求**放在最前面**，有些 provider（比如 Anthropic 的原生 API）是把 system 单独作为一个参数而不是放在 messages 里

# Agent Loop

> 个人理解:
>  比如用户输入一句话，但是包含多个任务，比如：看看最近一段的天气是不是变冷了，冷的就给我买一件外套。 可以拆开，第一个是查询天气，第二个是调用api购买外套；也有可能最近天气很好，不需要再购买外套。 agent loop就是在判断任务是否完成，在一直调用工具处理任务。
>
> 「不断感知执行结果、更新对任务的理解、决策下一步行动，并验证是否达到目标」的闭环。

```python
while not done:
    response = call_llm(messages)
    if response has tool_calls:
        results = execute_tools(response.tool_calls)
        messages.append(results)
    else:
        done = True
```

> LangChain 官方将这一模式总结为：“**Agent is just a model calling tools in a loop until a task is complete.**”



## 手写一个简易agent loop:

1. 实现 Tool Registry

   ```python
   def calculate(expression: str):
       return eval(expression)
   
   def get_weather():
       return {
           "city": "Singapore",
           "temperature": 28,
           "condition": "Cloudy"
       }
   
   
   # Tool Registry
   tools = {
       "calculate": calculate,
       "get_weather": get_weather
   }
   ```

   

2. 让 LLM 知道有哪些工具:把工具描述转换成 LLM 能理解的格式

   

3. 实现 Tool Executor

4. 发起请求,接收响应

5. 是否需要调用tool,

6. 调用tool excutor执行tool

7. 发送请求,接收响应

8. 循环重复,直到不需要调用工具.



现在我们的 Agent Loop 是：

```
LLM → Tool Call → Execute → Result → LLM
```

如果某个工具执行了 30 秒，期间 Agent 进程崩溃了，重启之后应该怎么办？

如果工具已经成功下单，但 Agent 没有收到返回结果，又应该怎么办？

这就涉及 Agent Runtime 的三个核心工程能力：

- State Persistence（状态持久化）
- Execution Recovery（执行恢复）
- Idempotency（幂等性）

# OPENAI两种api

| Responses API                  | Chat Completions API          |
| ------------------------------ | ----------------------------- |
| `response.output`              | `response.choices[0].message` |
| `item.type == "function_call"` | `message.tool_calls`          |
| `call.name`                    | `call.function.name`          |
| `call.arguments`               | `call.function.arguments`     |
| `call.call_id`                 | `call.id`                     |
| `function_call_output`         | `role="tool"`                 |
| `response.output_text`         | `message.content`             |

# MCP:

# 问题：

1. tool调用错误。

   实际定义了多个工具

   ```python
   
   @tool
   def calculate_shipping_cost(
       weight_kg : float = Field(description="包裹的重量，单位为千克"),
       destination : str = Field(description="目的地，例如：北京，上海，广州"),
       is_express : bool = Field(description="是否加急配送")
   ) -> str:
       """计算给定重量和目的地的快递的费用"""
           。。。
       return f"运费计算结果：{cost:.2f} 元（目的地：{destination}，重量：{weight_kg}kg，加急：{is_express}）"
   
   
   @tool
   def get_weather(city: str = Field(description="城市名称，例如：北京，上海，广州")) -> str:
       """获取指定城市的天气信息"""
       # 模拟获取天气信息
       return f"{city}的天气是晴天，温度25°C。"
   
   llm_with_tools = llm.bind_tools([calculate_shipping_cost, get_weather])
   
   
   query = HumanMessage("帮我计算一下邮寄5kg重量的衣服最快的速度到北京需要多少钱, 并且顺便告诉我北京的天气情况。")
   
   ```

   模型请求调用有：

   ```json
    [{'name': 'calculate_shipping_cost', 'args': {'weight_kg': 5, 'destination': '北京', 'is_express': True}, 'id': 'chatcmpl-tool-aed006361214d810', 'type': 'tool_call'}, {'name': 'get_weather', 'args': {'city': '北京'}, 'id': 'chatcmpl-tool-a84d227e74d38a1d', 'type': 'tool_call'}]
   ```

   但是最终回答：

   ```
   终回答: 您好！关于您的查询，结果如下：
   
   **📦 快递费用**
   - 目的地：北京
   - 重量：5.0 kg
   - 配送方式：加急（最快速度）
   - **费用：52.50 元**
   
   **🌤️ 北京天气**
   很抱歉，天气查询暂时未能成功获取到结果（系统提示查询中断）。建议您稍后再试，或直接通过天气应用/网站查看北京的实时天气。
   ```

   解决： 忘tm加到原本的本地调用函数中了，修改为下面

   ```python
   for tool_call in response.tool_calls:
       tool = tools_by_name.get(tool_call["name"])
       if tool:
           # 执行工具
           tool_result = tool.invoke(tool_call["args"])
           # 将工具执行结果封装为 ToolMessage 并添加到消息列表中
           messages.append(ToolMessage(content=tool_result, tool_name=tool_call["name"], tool_call_id=tool_call["id"]))
       else:
           print(f"未找到工具: {tool_call['name']}")
   ```

   
