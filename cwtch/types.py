from urllib.parse import urlparse


class SecretStr:
    __slots__ = ("_value",)

    def __init__(self, value):
        self._value = value

    def __str__(self):
        return f"{self.__class__.__name__}(***)"

    def __repr__(self):
        return f"{self.__class__.__name__}(***)"

    def __hash__(self):
        return hash(self._value)

    def __len__(self):
        return len(self._value)

    def get_secret_value(self):
        return self._value


class SecretUrl(SecretStr):
    __slots__ = ("_parsed",)

    def __init__(self, *args):
        super().__init__(*args)
        self._parsed = urlparse(self._value)

    def __str__(self):
        return f"{self.__class__.__name__}({self._parsed.scheme}://***@{self.netloc})"

    def __repr__(self):
        return f"{self.__class__.__name__}({self._parsed.scheme}://***@{self.netloc})"

    @property
    def scheme(self):
        return self._parsed.scheme

    @property
    def username(self):
        return "***" if self._parsed.username else None

    @property
    def password(self):
        return "***" if self._parsed.password else None

    @property
    def netloc(self):
        return self._parsed.netloc.rsplit("@", 1)[-1]

    @property
    def hostname(self):
        return self._parsed.hostname

    @property
    def portj(self):
        return self._parsed.port

    @property
    def path(self):
        return self._parsed.path

    @property
    def params(self):
        return self._parsed.params

    @property
    def query(self):
        return self._parsed.query

    @property
    def fragment(self):
        return self._parsed.fragment
