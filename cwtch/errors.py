from textwrap import indent


class Error(Exception):
    pass


class ValidationError(Error):
    def __init__(self, value, tp, errors: list[Exception], *, path: list | None = None, parameters=None):
        self.value = value
        self.type = tp
        self.errors = errors
        self.path = path
        self.parameters = parameters

    def __str__(self):
        errors = "\n".join(
            [indent(f"- {e}" if not isinstance(e, ValidationError) else f"{e}", "  ") for e in self.errors]
        )
        parameters, path = "", ""
        if self.parameters:
            parameters = f" parameters={list(self.parameters.values())}"
        if self.path:
            path = f" path={self.path}"
        return f"validation error for {self.type}{parameters}{path}\n{errors}"
