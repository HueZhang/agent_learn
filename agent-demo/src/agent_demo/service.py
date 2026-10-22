

from langchain_deepseek import ChatDeepSeek

from agent_demo.config import Settings
from agent_demo.schema import ResponseModel


class FeedbackService:

    def __init__(self, settings : Settings  ) -> None:
        self._settings = settings
        extra_body = (
            {"thinking" : {"type" : "disabled"}} if settings.disable_thinking else None
        )

        self._llm = ChatDeepSeek(
            model= settings.model,
            api_key= settings.api_key,
            base_url= settings.base_url,
            temperature= settings.temperature,
            max_tokens= settings.max_tokens,    
            max_retries= settings.max_retries,
            extra_body= extra_body
        )

        self._chain = self._llm.with_structured_output(ResponseModel)

    @property
    def model_name(self) -> str:
        return self._settings.model


    async def feedback(self,txt : str) -> ResponseModel:
        prompt = self._build_prompt(txt)

        result = await self._chain.ainvoke(prompt)

        if not isinstance(result, ResponseModel):
            raise UpstreamBadResponseError("模型返回非结构化结果")

        return result

    @staticmethod # 逻辑上属于这个类，但不需要访问类或实例的任何东西：
    def _build_prompt(txt:str) -> str:
        return (
            f"待分析文本:\n{txt}\n"
            f"请分析文本,并抽取信息,反馈并分类."
        )





class UpstreamBadResponseError(Exception):
    """模型结果结构化失败"""
