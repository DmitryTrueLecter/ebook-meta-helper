from ai.base import AIProvider

_PROVIDERS: dict[str, AIProvider] = {}


def register(provider: AIProvider) -> None:
    _PROVIDERS[provider.name] = provider


def get(name: str) -> AIProvider:
    return _PROVIDERS[name]
