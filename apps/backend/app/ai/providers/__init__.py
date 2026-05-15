from app.ai.registry import register
from app.ai.providers.dummy import DummyAIProvider
from app.ai.providers.openai_provider import OpenAIProvider

register(DummyAIProvider())
register(OpenAIProvider())
