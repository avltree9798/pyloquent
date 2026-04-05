"""Event dispatcher for model events."""

import asyncio
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Type

if TYPE_CHECKING:  # pragma: no cover
    from pyloquent.orm.model import Model


class EventDispatcher:
    """Event dispatcher for model lifecycle events.

    This class manages event listeners and dispatches events to them.
    It supports both class-level (static) and instance-level events.

    Example:
        # Register a listener
        User.on('creating', lambda model: print(f'Creating user: {model.name}'))

        # Register multiple listeners
        dispatcher = EventDispatcher()
        dispatcher.listen('saving', validate_model)
        dispatcher.listen('saved', log_changes)
    """

    _listeners: Dict[str, List[Callable]] = {}
    _model_listeners: Dict[Type, Dict[str, List[Callable]]] = {}

    @classmethod
    def listen(cls, event: str, callback: Callable) -> None:
        """Register an event listener globally.

        Args:
            event: Event name
            callback: Callback function
        """
        if event not in cls._listeners:
            cls._listeners[event] = []
        cls._listeners[event].append(callback)

    @classmethod
    def listen_for_model(cls, model_class: Type["Model"], event: str, callback: Callable) -> None:
        """Register an event listener for a specific model class.

        Args:
            model_class: Model class
            event: Event name
            callback: Callback function
        """
        if model_class not in cls._model_listeners:
            cls._model_listeners[model_class] = {}

        if event not in cls._model_listeners[model_class]:
            cls._model_listeners[model_class][event] = []

        cls._model_listeners[model_class][event].append(callback)

    @classmethod
    async def dispatch(cls, event: str, model: "Model", halt: bool = False) -> Any:
        """Dispatch an event to all listeners.

        Args:
            event: Event name
            model: Model instance
            halt: Whether to stop on first non-None response

        Returns:
            Response from last listener or first non-None if halt=True
        """
        # Get global listeners
        listeners = cls._listeners.get(event, [])

        # Get model-specific listeners
        model_listeners = cls._model_listeners.get(model.__class__, {}).get(event, [])

        all_listeners = listeners + model_listeners

        result = None
        for listener in all_listeners:
            try:
                if asyncio.iscoroutinefunction(listener):
                    response = await listener(model)
                else:
                    response = listener(model)

                if halt and response is not None:
                    return response

                result = response
            except Exception as e:
                # Log error but continue with other listeners
                print(f"Event listener error for {event}: {e}")

        return result

    @classmethod
    def forget(cls, event: str) -> None:
        """Remove all listeners for an event.

        Args:
            event: Event name
        """
        cls._listeners.pop(event, None)

    @classmethod
    def forget_model(cls, model_class: Type["Model"], event: str = None) -> None:
        """Remove listeners for a model.

        Args:
            model_class: Model class
            event: Specific event to forget, or all if None
        """
        if model_class not in cls._model_listeners:
            return

        if event:
            cls._model_listeners[model_class].pop(event, None)
        else:
            del cls._model_listeners[model_class]

    @classmethod
    def has_listeners(cls, event: str) -> bool:
        """Check if event has listeners.

        Args:
            event: Event name

        Returns:
            True if has listeners
        """
        return len(cls._listeners.get(event, [])) > 0

    @classmethod
    def model_has_listeners(cls, model_class: Type["Model"], event: str) -> bool:
        """Check if model has listeners for event.

        Args:
            model_class: Model class
            event: Event name

        Returns:
            True if has listeners
        """
        return len(cls._model_listeners.get(model_class, {}).get(event, [])) > 0

