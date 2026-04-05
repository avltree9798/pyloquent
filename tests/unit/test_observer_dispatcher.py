"""Unit tests for ModelObserver, observes decorator, and EventDispatcher."""
import pytest
from pyloquent.observers.observer import ModelObserver, observes
from pyloquent.observers.dispatcher import EventDispatcher


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _FakeModel:
    """Minimal stand-in for a Model instance."""
    id = 1
    name = "test"
    __class__ = type("FakeModel", (), {"__name__": "FakeModel"})


# ---------------------------------------------------------------------------
# ModelObserver
# ---------------------------------------------------------------------------

class TestModelObserver:
    def test_all_event_methods_exist(self):
        obs = ModelObserver()
        for event in ("creating", "created", "updating", "updated",
                      "saving", "saved", "deleting", "deleted",
                      "restoring", "restored", "force_deleting",
                      "force_deleted", "retrieved"):
            assert hasattr(obs, event), f"Missing: {event}"

    def test_base_methods_return_none(self):
        obs = ModelObserver()
        m = _FakeModel()
        assert obs.creating(m) is None
        assert obs.created(m) is None
        assert obs.updating(m) is None
        assert obs.updated(m) is None
        assert obs.saving(m) is None
        assert obs.saved(m) is None
        assert obs.deleting(m) is None
        assert obs.deleted(m) is None
        assert obs.restoring(m) is None
        assert obs.restored(m) is None
        assert obs.force_deleting(m) is None
        assert obs.force_deleted(m) is None
        assert obs.retrieved(m) is None

    def test_get_callbacks_returns_all_events(self):
        obs = ModelObserver()
        callbacks = obs._get_callbacks()
        assert "creating" in callbacks
        assert "deleted" in callbacks
        assert "retrieved" in callbacks
        assert len(callbacks) == 13

    def test_subclass_overrides_are_included(self):
        fired = []

        class MyObserver(ModelObserver):
            def creating(self, model):
                fired.append("creating")
                return "ok"

        obs = MyObserver()
        callbacks = obs._get_callbacks()
        assert "creating" in callbacks
        callbacks["creating"](_FakeModel())
        assert fired == ["creating"]


# ---------------------------------------------------------------------------
# observes decorator
# ---------------------------------------------------------------------------

class TestObservesDecorator:
    def test_marks_events_on_function(self):
        @observes("creating", "updating")
        def validate(model):
            pass

        assert hasattr(validate, "_observes_events")
        assert validate._observes_events == ("creating", "updating")

    def test_function_still_callable(self):
        called = []

        @observes("creating")
        def handler(model):
            called.append(model)

        handler("x")
        assert called == ["x"]


# ---------------------------------------------------------------------------
# EventDispatcher
# ---------------------------------------------------------------------------

class TestEventDispatcher:
    def setup_method(self):
        """Clear all listeners before each test."""
        EventDispatcher._listeners.clear()
        EventDispatcher._model_listeners.clear()

    def teardown_method(self):
        EventDispatcher._listeners.clear()
        EventDispatcher._model_listeners.clear()

    @pytest.mark.asyncio
    async def test_global_listener_fires(self):
        fired = []
        EventDispatcher.listen("creating", lambda m: fired.append(m))
        m = _FakeModel()
        await EventDispatcher.dispatch("creating", m)
        assert m in fired

    @pytest.mark.asyncio
    async def test_model_listener_fires(self):
        fired = []

        class MyModel:
            pass

        inst = MyModel()
        EventDispatcher.listen_for_model(MyModel, "created", lambda m: fired.append(m))
        await EventDispatcher.dispatch("created", inst)
        assert inst in fired

    @pytest.mark.asyncio
    async def test_forget_removes_global_listener(self):
        fired = []
        EventDispatcher.listen("saving", lambda m: fired.append(m))
        EventDispatcher.forget("saving")
        await EventDispatcher.dispatch("saving", _FakeModel())
        assert fired == []

    @pytest.mark.asyncio
    async def test_forget_model_removes_specific_event(self):
        fired = []

        class M:
            pass

        EventDispatcher.listen_for_model(M, "deleting", lambda m: fired.append(m))
        EventDispatcher.forget_model(M, "deleting")
        await EventDispatcher.dispatch("deleting", M())
        assert fired == []

    @pytest.mark.asyncio
    async def test_forget_model_all_events(self):
        fired = []

        class M:
            pass

        EventDispatcher.listen_for_model(M, "saving", lambda m: fired.append(m))
        EventDispatcher.listen_for_model(M, "saved", lambda m: fired.append(m))
        EventDispatcher.forget_model(M)
        await EventDispatcher.dispatch("saving", M())
        await EventDispatcher.dispatch("saved", M())
        assert fired == []

    def test_has_listeners_true(self):
        EventDispatcher.listen("retrieved", lambda m: None)
        assert EventDispatcher.has_listeners("retrieved") is True

    def test_has_listeners_false(self):
        assert EventDispatcher.has_listeners("nonexistent") is False

    def test_model_has_listeners_true(self):
        class M:
            pass
        EventDispatcher.listen_for_model(M, "updated", lambda m: None)
        assert EventDispatcher.model_has_listeners(M, "updated") is True

    def test_model_has_listeners_false(self):
        class M:
            pass
        assert EventDispatcher.model_has_listeners(M, "updated") is False

    @pytest.mark.asyncio
    async def test_listener_returning_false_propagates(self):
        EventDispatcher.listen("deleting", lambda m: False)
        result = await EventDispatcher.dispatch("deleting", _FakeModel())
        assert result is False

    @pytest.mark.asyncio
    async def test_async_listener_is_awaited(self):
        fired = []

        async def handler(m):
            fired.append(m)

        m = _FakeModel()
        EventDispatcher.listen("created", handler)
        await EventDispatcher.dispatch("created", m)
        assert m in fired

    @pytest.mark.asyncio
    async def test_no_listeners_returns_none(self):
        result = await EventDispatcher.dispatch("untouched", _FakeModel())
        assert result is None

    @pytest.mark.asyncio
    async def test_forget_model_noop_when_not_registered(self):
        class M:
            pass
        # Should not raise
        EventDispatcher.forget_model(M)
