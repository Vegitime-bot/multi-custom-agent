"""
backend/api/deps.py - 공통 의존성 주입
"""
from fastapi import Request

from backend.managers.chatbot_manager import ChatbotManager
from backend.managers.memory_manager import MemoryManager
from backend.managers.session_manager import SessionManager
from backend.retrieval.ingestion_client import IngestionClient


def get_chatbot_manager(request: Request) -> ChatbotManager:
    return request.app.state.chatbot_manager


def get_session_manager(request: Request) -> SessionManager:
    return request.app.state.session_manager


def get_memory_manager(request: Request) -> MemoryManager:
    return request.app.state.memory_manager


def get_ingestion_client(request: Request) -> IngestionClient:
    return request.app.state.ingestion_client
