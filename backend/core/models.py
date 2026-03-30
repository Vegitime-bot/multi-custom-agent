from __future__ import annotations
"""
core/models.py - 도메인 모델
ChatbotDef, Session, Message, ExecutionContext 등 핵심 데이터 구조를 정의한다.
"""


from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ── 실행 역할 ──────────────────────────────────────────────────────
class ExecutionRole(str, Enum):
    TOOL  = "tool"
    AGENT = "agent"


# ── 챗봇 정의 (선언형 JSON → Python 객체) ─────────────────────────
@dataclass
class RetrievalConfig:
    db_ids: list[str]
    k: int = 5
    filter_metadata: dict = field(default_factory=dict)


@dataclass
class LLMConfig:
    model: str
    temperature: float = 0.3
    max_tokens: int = 1024
    stream: bool = True


@dataclass
class MemoryConfig:
    enabled: bool = True
    max_messages: int = 20


@dataclass
class SubChatbotRef:
    """상위 챗봇이 참조하는 하위 챗봇 정보"""
    id: str
    level: int
    default_role: ExecutionRole


@dataclass
class ChatbotDef:
    """관리자가 선언형으로 등록한 챗봇 명세"""
    id: str
    name: str
    description: str
    role: ExecutionRole
    active: bool
    retrieval: RetrievalConfig
    llm: LLMConfig
    memory: MemoryConfig
    system_prompt: str
    sub_chatbots: list[SubChatbotRef] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "ChatbotDef":
        return cls(
            id=data["id"],
            name=data["name"],
            description=data.get("description", ""),
            role=ExecutionRole(data.get("role", "agent")),
            active=data.get("active", True),
            retrieval=RetrievalConfig(
                db_ids=data["retrieval"]["db_ids"],
                k=data["retrieval"].get("k", 5),
                filter_metadata=data["retrieval"].get("filter_metadata", {}),
            ),
            llm=LLMConfig(
                model=data["llm"]["model"],
                temperature=data["llm"].get("temperature", 0.3),
                max_tokens=data["llm"].get("max_tokens", 1024),
                stream=data["llm"].get("stream", True),
            ),
            memory=MemoryConfig(
                enabled=data["memory"].get("enabled", True),
                max_messages=data["memory"].get("max_messages", 20),
            ),
            system_prompt=data.get("system_prompt", ""),
            sub_chatbots=[
                SubChatbotRef(
                    id=s["id"],
                    level=s["level"],
                    default_role=ExecutionRole(s["default_role"]),
                )
                for s in data.get("sub_chatbots", [])
            ],
        )

    def to_dict(self) -> dict:
        return {
            "id":          self.id,
            "name":        self.name,
            "description": self.description,
            "role":        self.role.value,
            "active":      self.active,
            "retrieval": {
                "db_ids":          self.retrieval.db_ids,
                "k":               self.retrieval.k,
                "filter_metadata": self.retrieval.filter_metadata,
            },
            "llm": {
                "model":       self.llm.model,
                "temperature": self.llm.temperature,
                "max_tokens":  self.llm.max_tokens,
                "stream":      self.llm.stream,
            },
            "memory": {
                "enabled":      self.memory.enabled,
                "max_messages": self.memory.max_messages,
            },
            "system_prompt": self.system_prompt,
            "sub_chatbots": [
                {"id": s.id, "level": s.level, "default_role": s.default_role.value}
                for s in self.sub_chatbots
            ],
        }


# ── 메시지 ─────────────────────────────────────────────────────────
@dataclass
class Message:
    role: str   # "user" | "assistant" | "system"
    content: str

    def to_dict(self) -> dict:
        return {"role": self.role, "content": self.content}


# ── 세션 ───────────────────────────────────────────────────────────
@dataclass
class ChatSession:
    session_id: str
    chatbot_id: str
    user_knox_id: str
    role_override: dict[str, ExecutionRole] = field(default_factory=dict)
    active_level: int = 1

    def to_dict(self) -> dict:
        return {
            "session_id":    self.session_id,
            "chatbot_id":    self.chatbot_id,
            "user_knox_id":  self.user_knox_id,
            "role_override": {k: v.value for k, v in self.role_override.items()},
            "active_level":  self.active_level,
        }


# ── 실행 컨텍스트 (Factory가 생성하는 런타임 객체) ─────────────────
@dataclass
class ExecutionContext:
    chatbot_def: ChatbotDef
    session: ChatSession
    authorized_db_ids: list[str]     # chatbot_scope ∩ user_scope
    effective_role: ExecutionRole
    history: list[Message] = field(default_factory=list)

    @property
    def chatbot_id(self) -> str:
        return self.chatbot_def.id

    @property
    def session_id(self) -> str:
        return self.session.session_id
