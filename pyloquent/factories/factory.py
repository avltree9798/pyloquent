"""Model factory for generating test data."""

import asyncio
import random
import string
from abc import ABC, abstractmethod
from datetime import date, datetime, timedelta
from typing import Any, Callable, Dict, Generic, List, Optional, Type, TypeVar, Union

from pyloquent.orm.collection import Collection
from pyloquent.orm.model import Model

T = TypeVar("T", bound=Model)


class Factory(ABC, Generic[T]):
    """Base class for model factories.

    Factories provide a convenient way to generate test data with
    sensible defaults that can be overridden as needed.

    Example:
        class UserFactory(Factory[User]):
            model = User

            def definition(self) -> Dict[str, Any]:
                return {
                    'name': self.faker.name(),
                    'email': self.faker.email(),
                    'age': random.randint(18, 65),
                }

        # Create a single model
        user = await UserFactory.create()

        # Create multiple models
        users = await UserFactory.create_many(10)

        # Override defaults
        user = await UserFactory.create(name='John Doe')

        # Create without saving
        user = UserFactory.make()
    """

    model: Type[T]
    _faker: Any = None
    _count: int = 1

    def __init__(self):
        """Initialize the factory."""
        pass

    @property
    def faker(self) -> Any:
        """Get the Faker instance for generating fake data.

        Returns:
            Faker instance
        """
        if self._faker is None:
            try:
                from faker import Faker

                self._faker = Faker()
            except ImportError:
                raise ImportError(
                    "Factory requires 'faker' package. Install with: pip install faker"
                )
        return self._faker

    @abstractmethod
    def definition(self) -> Dict[str, Any]:
        """Define the default attributes for the model.

        Returns:
            Dictionary of default attributes
        """
        pass

    def state(self, state: Dict[str, Any]) -> "Factory[T]":
        """Set a specific state for the factory.

        Args:
            state: State attributes to merge

        Returns:
            Self for chaining
        """
        self._state = state
        return self

    def count(self, count: int) -> "Factory[T]":
        """Set the number of models to create.

        Args:
            count: Number of models

        Returns:
            Self for chaining
        """
        self._count = count
        return self

    def sequence(self, callback: Callable[[int], Dict[str, Any]]) -> "Factory[T]":
        """Define a sequence callback for generating sequential data.

        Args:
            callback: Function that receives the sequence number

        Returns:
            Self for chaining
        """
        self._sequence_callback = callback
        return self

    def make(self, overrides: Optional[Dict[str, Any]] = None) -> T:
        """Make a model instance without saving.

        Args:
            overrides: Attributes to override

        Returns:
            Model instance
        """
        attributes = self._get_attributes(overrides)
        return self.model(**attributes)

    def make_many(self, count: int, overrides: Optional[Dict[str, Any]] = None) -> List[T]:
        """Make multiple model instances without saving.

        Args:
            count: Number of models
            overrides: Attributes to override

        Returns:
            List of model instances
        """
        return [self.make(overrides) for _ in range(count)]

    async def create(self, overrides: Optional[Dict[str, Any]] = None) -> T:
        """Create and save a model.

        Args:
            overrides: Attributes to override

        Returns:
            Saved model instance
        """
        instance = self.make(overrides)
        await instance.save()
        return instance

    async def create_many(
        self, count: int, overrides: Optional[Dict[str, Any]] = None
    ) -> Collection[T]:
        """Create and save multiple models.

        Args:
            count: Number of models
            overrides: Attributes to override

        Returns:
            Collection of saved model instances
        """
        instances = []
        for _ in range(count):
            instance = await self.create(overrides)
            instances.append(instance)
        return Collection(instances)

    def _get_attributes(self, overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Get the merged attributes.

        Args:
            overrides: Attributes to override

        Returns:
            Merged attributes dictionary
        """
        attributes = self.definition()

        # Apply state if defined
        if hasattr(self, "_state"):
            attributes.update(self._state)

        # Apply overrides
        if overrides:
            attributes.update(overrides)

        return attributes

    # Helper methods for common data types
    def random_int(self, min: int = 0, max: int = 100) -> int:
        """Generate a random integer.

        Args:
            min: Minimum value
            max: Maximum value

        Returns:
            Random integer
        """
        return random.randint(min, max)

    def random_float(self, min: float = 0.0, max: float = 100.0) -> float:
        """Generate a random float.

        Args:
            min: Minimum value
            max: Maximum value

        Returns:
            Random float
        """
        return random.uniform(min, max)

    def random_string(self, length: int = 10) -> str:
        """Generate a random string.

        Args:
            length: String length

        Returns:
            Random string
        """
        return "".join(random.choices(string.ascii_letters + string.digits, k=length))

    def random_bool(self) -> bool:
        """Generate a random boolean.

        Returns:
            Random boolean
        """
        return random.choice([True, False])

    def random_date(self, start: date = None, end: date = None) -> date:
        """Generate a random date.

        Args:
            start: Start date
            end: End date

        Returns:
            Random date
        """
        if start is None:
            start = date(1970, 1, 1)
        if end is None:
            end = date.today()

        days = (end - start).days
        random_days = random.randint(0, days)
        return start + timedelta(days=random_days)

    def random_datetime(self, start: datetime = None, end: datetime = None) -> datetime:
        """Generate a random datetime.

        Args:
            start: Start datetime
            end: End datetime

        Returns:
            Random datetime
        """
        if start is None:
            start = datetime(1970, 1, 1)
        if end is None:
            end = datetime.now()

        delta = end - start
        random_seconds = random.randint(0, int(delta.total_seconds()))
        return start + timedelta(seconds=random_seconds)

    def random_choice(self, choices: List[Any]) -> Any:
        """Pick a random choice from a list.

        Args:
            choices: List of choices

        Returns:
            Random choice
        """
        return random.choice(choices)

    def random_choices(self, choices: List[Any], count: int) -> List[Any]:
        """Pick multiple random choices from a list.

        Args:
            choices: List of choices
            count: Number to pick

        Returns:
            List of random choices
        """
        return random.choices(choices, k=count)

    @classmethod
    async def create_batch(cls, count: int, **overrides) -> Collection[T]:
        """Create multiple models in a batch.

        Args:
            count: Number of models
            **overrides: Attributes to override

        Returns:
            Collection of saved model instances
        """
        factory = cls()
        return await factory.create_many(count, overrides)

    @classmethod
    def make_batch(cls, count: int, **overrides) -> List[T]:
        """Make multiple models without saving.

        Args:
            count: Number of models
            **overrides: Attributes to override

        Returns:
            List of model instances
        """
        factory = cls()
        return factory.make_many(count, overrides)


class Sequence:
    """Helper class for generating sequential values."""

    def __init__(self, start: int = 1):
        """Initialize the sequence.

        Args:
            start: Starting value
        """
        self._value = start

    def __call__(self) -> int:
        """Get the next value in the sequence.

        Returns:
            Next sequence value
        """
        value = self._value
        self._value += 1
        return value

    def reset(self, start: int = 1) -> None:
        """Reset the sequence.

        Args:
            start: New starting value
        """
        self._value = start
