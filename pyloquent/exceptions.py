"""Custom exceptions for Pyloquent."""


class PyloquentException(Exception):
    """Base exception for all Pyloquent errors."""

    pass


class QueryException(PyloquentException):
    """Exception raised for errors in SQL query execution."""

    def __init__(self, message: str, sql: str = "", bindings: list = None):
        """Initialize the exception with query details.

        Args:
            message: Error message
            sql: The SQL query that caused the error
            bindings: Query bindings
        """
        super().__init__(message)
        self.sql = sql
        self.bindings = bindings or []


class ModelNotFoundException(PyloquentException):
    """Exception raised when a model cannot be found."""

    def __init__(self, model_class: type, identifier=None):
        """Initialize the exception.

        Args:
            model_class: The model class that was queried
            identifier: The identifier that was used to find the model
        """
        model_name = model_class.__name__ if hasattr(model_class, "__name__") else str(model_class)
        message = f"No query results for model [{model_name}]"
        if identifier is not None:
            message += f" with identifier [{identifier}]"
        super().__init__(message)
        self.model_class = model_class
        self.identifier = identifier


class RelationNotFoundException(PyloquentException):
    """Exception raised when a relation cannot be found."""

    def __init__(self, model_class: type, relation: str):
        """Initialize the exception.

        Args:
            model_class: The model class that was queried
            relation: The relation name that was not found
        """
        model_name = model_class.__name__ if hasattr(model_class, "__name__") else str(model_class)
        message = f"Relation [{relation}] not found on model [{model_name}]"
        super().__init__(message)
        self.model_class = model_class
        self.relation = relation


class MassAssignmentException(PyloquentException):
    """Exception raised when mass assignment protection blocks an operation."""

    def __init__(self, key: str, model_class: type):
        """Initialize the exception.

        Args:
            key: The attribute key that was attempted to be mass assigned
            model_class: The model class
        """
        model_name = model_class.__name__ if hasattr(model_class, "__name__") else str(model_class)
        message = f"Cannot mass assign attribute [{key}] on model [{model_name}]"
        super().__init__(message)
        self.key = key
        self.model_class = model_class
