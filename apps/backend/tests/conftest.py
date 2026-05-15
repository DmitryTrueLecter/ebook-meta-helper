import pytest


def pytest_collection_modifyitems(items):
    """Auto-mark tests by directory: unit/ → unit, integration/ → integration."""
    for item in items:
        path = str(item.fspath)
        if "/tests/unit/" in path or "\\tests\\unit\\" in path:
            item.add_marker(pytest.mark.unit)
        elif "/tests/integration/" in path or "\\tests\\integration\\" in path:
            item.add_marker(pytest.mark.integration)
