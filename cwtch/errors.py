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
        try:
            errors = "\n".join(
                [indent(f"E: {e}" if not isinstance(e, ValidationError) else f"{e}", "  ") for e in self.errors]
            )
            tp = self.type
            path = ""
            if self.parameters:
                origin = getattr(tp, "__origin__", tp)
                if hasattr(origin, "__typing_subst__"):
                    tp = origin.__typing_subst__(self.parameters[origin])
                else:
                    tp = origin[*self.parameters.values()]
            if self.path:
                path = f" path={self.path}"
            return f"type=[{tp}]{path} input_type=[{type(self.value)}]\n{errors}"
        except Exception as e:
            return f"cwtch internal error: {e}\noriginal errors: {self.errors}"
