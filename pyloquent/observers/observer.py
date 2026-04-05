"""Model observer base class."""

from typing import TYPE_CHECKING, Any, Callable, Type

if TYPE_CHECKING:  # pragma: no cover
    from pyloquent.orm.model import Model


class ModelObserver:
    """Base class for model observers.

    Observers provide a clean way to handle model events by grouping
    related event handlers in a single class.

    Example:
        class UserObserver(ModelObserver):
            async def creating(self, user: User) -> None:
                user.slug = slugify(user.name)

            async function created(self, user: User) -> None:
                await send_welcome_email(user)

            async function updating(self, user: User) -> None:
                if user.isDirty('email'):
                    user.email_verified_at = None

            async function deleted(self, user: User) -> None:
                await user.posts().update({'author_name': user.name})

        # Register observer
        User.observe(UserObserver())
    """

    def creating(self, model: "Model") -> Any:
        """Handle creating event (before insert)."""
        pass

    def created(self, model: "Model") -> Any:
        """Handle created event (after insert)."""
        pass

    def updating(self, model: "Model") -> Any:
        """Handle updating event (before update)."""
        pass

    def updated(self, model: "Model") -> Any:
        """Handle updated event (after update)."""
        pass

    def saving(self, model: "Model") -> Any:
        """Handle saving event (before insert or update)."""
        pass

    def saved(self, model: "Model") -> Any:
        """Handle saved event (after insert or update)."""
        pass

    def deleting(self, model: "Model") -> Any:
        """Handle deleting event (before delete)."""
        pass

    def deleted(self, model: "Model") -> Any:
        """Handle deleted event (after delete)."""
        pass

    def restoring(self, model: "Model") -> Any:
        """Handle restoring event (before soft delete restore)."""
        pass

    def restored(self, model: "Model") -> Any:
        """Handle restored event (after soft delete restore)."""
        pass

    def force_deleting(self, model: "Model") -> Any:
        """Handle force_deleting event (before force delete)."""
        pass

    def force_deleted(self, model: "Model") -> Any:
        """Handle force_deleted event (after force delete)."""
        pass

    def retrieved(self, model: "Model") -> Any:
        """Handle retrieved event (after model is fetched from DB)."""
        pass

    def _get_callbacks(self) -> dict:
        """Get all callback methods.

        Returns:
            Dict mapping event names to callback methods
        """
        events = [
            "creating",
            "created",
            "updating",
            "updated",
            "saving",
            "saved",
            "deleting",
            "deleted",
            "restoring",
            "restored",
            "force_deleting",
            "force_deleted",
            "retrieved",
        ]

        callbacks = {}
        for event in events:
            if hasattr(self, event):
                method = getattr(self, event)
                if callable(method):
                    callbacks[event] = method

        return callbacks


def observes(*events: str) -> Callable:
    """Decorator to mark a method as an observer for specific events.

    This is useful when you want to use a single method for multiple events
    or when you want to observe events on a function rather than a class.

    Example:
        @observes('creating', 'updating')
        def validate_user(user):
            if not user.name:
                raise ValueError("Name is required")

        User.on('creating', validate_user)
        User.on('updating', validate_user)

    Args:
        *events: Event names to observe

    Returns:
        Decorator function
    """

    def decorator(func: Callable) -> Callable:
        func._observes_events = events
        return func

    return decorator
