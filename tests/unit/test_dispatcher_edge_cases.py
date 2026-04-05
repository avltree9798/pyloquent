"""Unit tests for EventDispatcher edge cases: halt, exception in listener."""
import pytest
import asyncio
from pyloquent.observers.dispatcher import EventDispatcher


@pytest.fixture(autouse=True)
def reset_dispatcher():
    """Clear all listeners after each test to prevent pollution."""
    yield
    EventDispatcher._listeners.clear()
    EventDispatcher._model_listeners.clear()


# ---------------------------------------------------------------------------
# halt=True — stops after first non-None response
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_halt_returns_first_non_none_response():
    class FakeModel:
        pass

    EventDispatcher.listen("test_halt", lambda m: "stop")
    EventDispatcher.listen("test_halt", lambda m: "never")

    result = await EventDispatcher.dispatch("test_halt", FakeModel(), halt=True)
    assert result == "stop"


# ---------------------------------------------------------------------------
# Exception inside a listener is swallowed and dispatch continues
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_exception_in_listener_is_swallowed(capsys):
    class FakeModel:
        pass

    def bad_listener(m):
        raise RuntimeError("boom")

    results = []

    def good_listener(m):
        results.append("ok")

    EventDispatcher.listen("test_exc", bad_listener)
    EventDispatcher.listen("test_exc", good_listener)

    await EventDispatcher.dispatch("test_exc", FakeModel())
    assert "ok" in results
    captured = capsys.readouterr()
    assert "boom" in captured.out


# ---------------------------------------------------------------------------
# listen_for_model convenience helper
# ---------------------------------------------------------------------------

def test_listen_for_model_registers_listener():
    class FakeModel:
        pass

    called = []
    EventDispatcher.listen_for_model(FakeModel, "created", lambda m: called.append(1))
    assert EventDispatcher.model_has_listeners(FakeModel, "created") is True
