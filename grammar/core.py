from abc import ABC
from collections import defaultdict
from typing import Callable, Iterable, Iterator, Optional, Sequence, TypeGuard, cast

from utils.tokenizer import Token


class Symbol(ABC):
    """A symbol in a grammar;
    Each is identified by a unique ID"""

    def __init__(self, name: str) -> None:
        self.name = name

    def __hash__(self) -> int:
        return hash(self.name)

    def __str__(self):
        return self.name

    def __eq__(self, other):
        if not isinstance(other, Symbol):
            raise NotImplemented
        return self.name == other.name


class Terminal(Symbol):
    def __init__(self, label: str, token_matcher: Callable[[Token], bool]):
        super().__init__(label)
        self._token_matcher = token_matcher

    def matches(self, token: Token) -> bool:
        return self._token_matcher(token)

    def __repr__(self):
        return f"[bold blue]{self.name}[/bold blue]"


class Marker(Terminal):
    def __repr__(self):
        return f"[bold cyan]{self.name}[/bold cyan]"


EOF = Marker("eof", lambda token: token.token_type == "eof")
EMPTY = Marker("ε", lambda token: True)


class NonTerminal(Symbol):
    def __repr__(self):
        return f"[bold red]<{self.name.capitalize()}>[/bold red]"


def all_terminals(symbols: Sequence[Symbol]) -> TypeGuard[Sequence[Terminal]]:
    return all(isinstance(symbol, Terminal) for symbol in symbols)


class Expansion(list[Symbol]):
    def __init__(self, args: Optional[Iterable[Symbol]] = None):
        if args is None:
            args = []
        super().__init__(args)

    def __iter__(self):
        yield from filter(lambda token: token is not EMPTY, super().__iter__())

    def matches(self, tokens: Sequence[Token]) -> bool:
        if len(self) == len(tokens):
            if all_terminals(self):
                return all(
                    terminal.matches(token) for terminal, token in zip(self, tokens)
                )
        return False

    def perform_derivation(self, index, replacer: "Expansion") -> "Expansion":
        if not replacer:
            return Expansion(self[:index] + self[index + 1 :])
        return Expansion(self[:index] + replacer + self[index + 1 :])

    def append_marker(self, sentinel: Marker):
        return Expansion(self + [sentinel])

    def enumerate_variables(self) -> Iterator[tuple[int, NonTerminal]]:
        for index, symbol in enumerate(self):
            if isinstance(symbol, NonTerminal):
                yield index, symbol

    def should_prune(
        self,
        tokens: Sequence[Token],
        seen: set["Expansion"],
        nullable_set: set[Symbol],
    ) -> bool:
        # if this is a sentential form we have explored, just ignore it
        if self in seen:
            return True

        # if we have more non-nullables than the number of tokens
        # we should prune
        if len(tuple(filter(lambda sym: sym not in nullable_set, self))) > len(tokens):
            return True

        # if we have a prefix of terminals which doesn't match the tokens
        # we should prune
        for (symbol, token) in zip(self, tokens):
            if isinstance(symbol, Terminal):
                if not symbol.matches(token):
                    return True
            else:
                break
        else:
            # if the sentential form is a PROPER prefix of the tokens
            # we should prune
            return len(self) != len(tokens)

        # if any of the tokens in the sentential form is not in the tokens,
        # we should prune
        for terminal in filter(lambda item: isinstance(item, Terminal), self):
            if not any(cast(Terminal, terminal).matches(token) for token in tokens):
                return True
        return False

    def __hash__(self):
        return hash(tuple(self))

    def __len__(self):
        return super().__len__() - self.count(EMPTY)

    def __str__(self):
        return f'{"".join(str(item) for item in super().__iter__())}'

    def __repr__(self):
        return f'{"".join(repr(item) for item in super().__iter__())}'


FollowSet = defaultdict[Symbol, set[Terminal]]
FirstSet = defaultdict[Symbol, set[Terminal]]
NullableSet = set[Symbol]


class Definition(list[Expansion]):
    def __init__(self, expansions: Optional[Iterable[Expansion]] = None):
        if expansions is None:
            expansions = []
        super().__init__(expansions)

    def __repr__(self):
        return " | ".join(repr(item) for item in self)

    def __hash__(self):
        return hash(tuple(self))