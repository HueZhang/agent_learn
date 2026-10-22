
import tomllib
from functools import lru_cache
from pathlib import Path

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    ValidationError,
    field_validator,
)

# 配置文件路径
PROJECT_ROOT = Path(__file__).parent.parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT/"config.toml"

class Settings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid") 
    """
    frozen : 实例不可变；创建后不能再修改字段值，并且自动生成__hash__,实例可以被哈希（能放进 set、当 dict 的 key)。
    extra="forbid" 禁止多余字段。 ignore：静默丢弃多余字段  allow：保留多余字段，存放在实例上（通过model_extra 访问）
    """
    api_key: SecretStr # 显式调用 .get_secret_value() 才能拿到真实内容
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-flash"

    temperature: float = Field(default=0.0, ge=0.0, le=2.0) # 控制输出的随机性/创造性 
    max_tokens: int = Field(default=512, gt=0) # 限制模型单次回复最多生成多少个 token
    timeout_seconds: float = Field(default=30.0, gt=0) 
    max_retries: int = Field(default=1, ge=0, le=5) 

    # DeepSeek 思考模式不支持强制 tool_choice，而结构化输出依赖它。
    # 开启时通过 extra_body 关闭思考模式；换成不支持该参数的模型时请设为 false。
    disable_thinking: bool = True


    @field_validator("api_key")
    @classmethod # 必须写,且放在field_validator 后面
    def _api_key_not_blank(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().strip():
            raise ValueError("api_key 不能为空，请在 config.toml 中填写")
        return value

    @field_validator("base_url")
    @classmethod
    def _valid_base_url(cls, value: str) -> str:
        if not value.startswith(("http://", "https://")):
            raise ValueError("base_url 必须以 http:// 或 https:// 开头")
        return value.rstrip("/")

    @field_validator("model")
    @classmethod
    def _model_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("model 不能为空")
        return value.strip()



"""
单例
"""
@lru_cache(maxsize=1)
def get_settings() -> Settings:
    path = DEFAULT_CONFIG_PATH
    if not path.exists():
        raise RuntimeError(
            f"找不到配置文件{path}"
        )


    try:
        with path.open("rb") as fh:
            raw = tomllib.load(fh)
    except tomllib.TOMLDecodeError as ex:
        raise RuntimeError(f"配置文件{path},不是合法的TOML:{ex}") from ex # 异常链，明确声明新异常由旧异常引出


    try:
        return Settings.model_validate(raw)
    except ValidationError as ex:
        raise RuntimeError(f"配置文件{path}校验失败：\n{ex}") from ex
