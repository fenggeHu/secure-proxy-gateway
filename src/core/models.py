import re
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class TimeoutConfig(BaseModel):
    connect: float = 5.0
    read: float = 30.0
    write: float = 30.0


class ProxyConfig(BaseModel):
    timeout: TimeoutConfig = Field(default_factory=TimeoutConfig)
    max_response_size: int = 10 * 1024 * 1024  # 10MB
    strip_headers: List[str] = Field(
        default_factory=lambda: [
            "Host",
            "Connection",
            "Transfer-Encoding",
            "Upgrade",
            "Proxy-Connection",
            "Proxy-Authenticate",
            "Proxy-Authorization",
        ]
    )


class ServerConfig(BaseModel):
    port: int = 8000
    host: str = "127.0.0.1"
    admin_host: str = "127.0.0.1"


class RequestRules(BaseModel):
    add_params: Dict[str, str] = Field(default_factory=dict)
    add_headers: Dict[str, str] = Field(default_factory=dict)
    del_params: List[str] = Field(default_factory=list)


class MaskRule(BaseModel):
    pattern: str
    replacement: str

    @field_validator("pattern")
    @classmethod
    def validate_pattern(cls, value: str) -> str:
        if len(value) > 500:
            raise ValueError("正则表达式长度不能超过 500 字符")
        try:
            re.compile(value)
        except re.error as exc:
            raise ValueError(f"无效的正则表达式: {exc}")
        return value


class ResponseRules(BaseModel):
    mask_regex: List[MaskRule] = Field(default_factory=list)


class RouteConfig(BaseModel):
    name: str
    path: str
    target: str
    method: str = "*"
    description: Optional[str] = None
    request_rules: RequestRules = Field(default_factory=RequestRules)
    response_rules: ResponseRules = Field(default_factory=ResponseRules)

    @field_validator("path")
    @classmethod
    def ensure_leading_slash(cls, value: str) -> str:
        if not value.startswith("/"):
            raise ValueError("path 必须以 / 开头")
        return value.rstrip("/") or "/"

    @field_validator("method")
    @classmethod
    def normalize_method(cls, value: str) -> str:
        return value.upper()


class SystemConfig(BaseModel):
    server: ServerConfig = Field(default_factory=ServerConfig)
    proxy: ProxyConfig = Field(default_factory=ProxyConfig)
    routes: List[RouteConfig] = Field(default_factory=list)
