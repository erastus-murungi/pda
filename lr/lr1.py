from functools import cache
from typing import NamedTuple

from grammar.core import EMPTY, EOF, NonTerminal, Rule, Symbol, Terminal
from lr.core import Accept, Goto, LRTable, Reduce, Shift, LRState


class LR1Item(NamedTuple):
    name: NonTerminal
    dot: int
    rule: Rule
    lookahead: Terminal

    def __repr__(self):
        return (
            f"{self.name!r} -> {' '.join(repr(sym) for sym in self.rule[:self.dot])}"
            f" . "
            f"{' '.join(repr(sym) for sym in self.rule[self.dot:])}         ({self.lookahead!r})"
        )

    def __str__(self):
        return (
            f"{self.name!s} -> {' '.join(str(sym) for sym in self.rule[:self.dot])}"
            f" . "
            f"{' '.join(str(sym) for sym in self.rule[self.dot:])}          ({self.lookahead!s})"
        )

    def advance(self):
        return LR1Item(self.name, self.dot + 1, self.rule, self.lookahead)

    def completed(self):
        return self.dot >= len(self.rule)


class LR1ParsingTable(LRTable[LR1Item]):
    def init_kernel(self):
        return LRState[LR1Item](
            LR1Item(
                self.grammar.start_symbol,
                0,
                self.grammar[self.grammar.start_symbol][0].append_marker(EOF),
                EOF,  # could be anything
            ),
            cls=LR1Item,
        )

    @cache
    def closure(self, configuration_set: LRState[LR1Item]) -> LRState[LR1Item]:
        """
        Compute the closure of LR(1) item set
        :param configuration_set: a set of LR(1) items
        :return: closure of the set
        """

        items = configuration_set.copy()
        changing = True
        while changing:
            changing = False
            for _, dot, rule, lookahead in items.yield_unfinished():
                x, beta = rule[dot], rule[dot + 1 :]
                if isinstance(x, NonTerminal):
                    initial_size = len(items)
                    for gamma in self.grammar[x]:
                        for w in self.grammar.first_sentential_form(beta + [lookahead]):
                            items.append(LR1Item(x, 0, gamma, w))
                    changing = len(items) != initial_size
        return items

    @cache
    def goto(
        self, configuration_set: LRState[LR1Item], sym: Symbol
    ) -> LRState[LR1Item]:
        """Compute the goto set of LR(1) item set"""
        assert sym is not EMPTY
        new_items = LRState[LR1Item](cls=LR1Item)
        for item in configuration_set.yield_unfinished():
            if item.rule[item.dot] == sym:
                new_items.append(item.advance())
        return self.closure(new_items)

    def compute_reduce_actions(self):
        for state in self.states:
            for name, _, rule, lookahead in state.yield_finished():
                if (state, lookahead.id) not in self:
                    self[(state, lookahead.id)] = Reduce(name, rule)
                else:
                    raise ValueError(
                        f"Encountered shift/reduce conflict on \n"
                        f" state: {str(state)}\n and symbol: {lookahead.id}\n"
                        f"  {self[(state, lookahead.id)]} and \n"
                        f"  Reduce({name!s} -> {rule!s})"
                    )

    def get_items(self) -> list[LRState[LR1Item]]:
        lr1_items = {self.closure(self.init_kernel()): None}
        changing = True
        while changing:
            changing = False
            for state in lr1_items.copy():
                for X in self.grammar.non_terminals | self.grammar.terminals:
                    next_set = self.goto(state, X)
                    if next_set and next_set not in lr1_items:
                        changing = True
                        lr1_items[self.goto(state, X)] = None
        return list(lr1_items)

    def construct(self):
        items = self.get_items()

        for i, state_i in enumerate(items):
            for item in state_i:
                if item.completed():
                    if item.name == self.grammar.start_symbol and item.lookahead is EOF:
                        self[(state_i, EOF.id)] = Accept()
                    elif item.name != self.grammar.start_symbol:
                        self[(state_i, item.lookahead.id)] = Reduce(
                            item.name, item.rule
                        )
                else:
                    a = item.rule[item.dot]
                    for I_j in items:
                        if self.goto(state_i, a) == I_j:
                            self[(state_i, a.id)] = Shift(I_j)
            for nt in self.grammar.non_terminals:
                for I_j in items:
                    if self.goto(state_i, nt) == I_j:
                        self[(state_i, nt.id)] = Goto(I_j)

        self.states = items


if __name__ == "__main__":
    from rich import print as print_rich
    from rich.pretty import pretty_repr

    from utils.parse_grammar import parse_grammar

    # table = {
    #     "x": "x",
    #     "(": "(",
    #     ")": ")",
    #     ",": ",",
    # }
    # g = """
    #         <S'>
    #         <S'> -> <S>
    #         <S> -> (<L>)
    #         <L> -> <S>
    #         <S> -> x
    #         <L> -> <L>,<S>
    # """

    # table = {"+": "+", "(": "(", ")": ")"}
    #
    # g = """
    #     <S>
    #     <S> -> <E>
    #     <E> -> <E> + <T>
    #     <E> -> <T>
    #     <T> -> ( <E> )
    #     <T> -> integer
    # """
    table = {
        "+": "+",
        "*": "*",
        "(": "(",
        ")": ")",
    }

    g = """
    <E'>
    <E'> -> <E>
    <E> -> <E>+<T>
    <E> -> <T>
    <T> -> <T>*<F>
    <T> -> <F>
    <F> -> (<E>)
    <F> -> integer

    """

    cfg = parse_grammar(g, table)
    print_rich(pretty_repr(cfg))

    p = LR1ParsingTable(cfg)
    p.draw_with_graphviz()
    print_rich(p.to_pretty_table())

    print_rich(pretty_repr(LR1ParsingTable(cfg)))
