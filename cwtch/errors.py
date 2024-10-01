from textwrap import indent
from typing import Any

from cwtch.config import SHOW_INPUT_VALUE_ON_ERROR


class Error(Exception):
    pass


class ValidationError(Error):
    def __init__(
        self,
        value,
        tp,
        errors: list[Exception],
        *,
        path: list | None = None,
        path_value: Any | None = None,
    ):
        self.value = value
        self.type = tp
        self.errors = errors
        self.path = path
        self.path_value = path_value

    def _sub_error_str(self, show_value: bool):
        try:
            sub_errors_show_value = show_value and len(self.errors) == 1
            errors = "\n".join(
                [
                    indent(
                        (
                            f"Error: {e}"
                            if not isinstance(e, ValidationError)
                            else f"{e._sub_error_str(sub_errors_show_value)}"
                        ),
                        "  ",
                    )
                    for e in self.errors
                ]
            )
            tp = self.type
            tp = f"{tp}".replace("typing.", "")
            path = ""
            if self.path:
                path = f" path[ {str(self.path)[1:-1]} ]"
            value = ""
            if show_value:
                if self.path:
                    value = f" path_value[ {repr(self.path_value)} ]"
                else:
                    value = f" value[ {repr(self.value)} ]"
            return f"type[ {tp} ]{path} value_type[ {type(self.value)} ]{value}\n{errors}"
        except Exception as e:
            return f"cwtch internal error: {e}\noriginal errors: {self.errors}"

    def __str__(self):
        try:
            show_value = SHOW_INPUT_VALUE_ON_ERROR
            sub_errors_show_value = show_value and len(self.errors) == 1
            show_value = show_value and (len(self.errors) > 1 or not isinstance(self.errors[0], ValidationError))
            errors = "\n".join(
                [
                    indent(
                        (
                            f"Error: {e}"
                            if not isinstance(e, ValidationError)
                            else f"{e._sub_error_str(sub_errors_show_value)}"
                        ),
                        "  ",
                    )
                    for e in self.errors
                ]
            )
            tp = self.type
            tp = f"{tp}".replace("typing.", "")
            path = ""
            if self.path:
                path = f" path[ {str(self.path)[1:-1]} ]"
            value = ""
            if show_value:
                if self.path:
                    value = f" path_value[ {repr(self.path_value)} ]"
                else:
                    value = f" value[ {repr(self.value)} ]"
            return f"type[ {tp} ]{path} value_type[ {type(self.value)} ]{value}\n{errors}"
        except Exception as e:
            return f"cwtch internal error: {e}\noriginal errors: {self.errors}"
