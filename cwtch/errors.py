from textwrap import indent

from rich import pretty

from cwtch import config


__all__ = ("Error", "ValidationError")


class Error(Exception):
    """Base class for all exceptions"""

    pass


class MissingValidatorError(Error):
    """Raised when no validator is registered for a type."""

    pass


class ValidationError(Error):
    """Raised when validation of a value fails.

    Attributes:
        value: The value that failed validation.
        type: The expected type.
        errors: List of validation errors.
        path: Path to the field in nested structures.
    """

    def __init__(
        self,
        value,
        tp,
        errors: list[Exception],
        *,
        path: list | None = None,
    ):
        self.value = value
        self.type = tp
        self.errors = errors
        self.path = path

    def __str__(self):
        try:
            lines = []

            if self.value != ... and self.type:
                lines.append(f"Type: {type(self.value)} --> " + f"{self.type}".replace("typing.", ""))
            elif self.value != ...:
                lines.append(f"Type: {type(self.value)} -->")
            elif self.type:
                # lines.append(f"Type: --> {self.type}".replace("typing.", ""))
                lines.append(f"Type: {self.type}".replace("typing.", ""))

            if config.SHOW_INPUT_VALUE_ON_ERROR and self.value != ...:
                lines.append(f"Input: {pretty.pretty_repr(self.value, max_length=10, max_string=100)}")

            if self.path:
                lines.append(f"Path: [{str(self.path)[1:-1]}]")

            errors = [
                indent(
                    (
                        f"{e.__class__.__name__}: {e}"
                        if not isinstance(e, ValidationError)
                        else f"{e.__class__.__name__}:{e}"
                    ),
                    "",
                )
                for e in self.errors
            ]

            lines.extend(errors)

            return indent("\n" + "\n".join(lines), "  ")

        except Exception as e:
            return f"cwtch internal error: {e}\noriginal errors: {self.errors}"

    def __repr__(self):
        return f"{self.__class__.__name__} {self}"
