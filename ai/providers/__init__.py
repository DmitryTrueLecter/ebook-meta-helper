from ai.registry import register
from ai.providers.dummy import DummyAIProvider
from ai.providers.openai_provider import OpenAIProvider

register(DummyAIProvider())
register(OpenAIProvider())
