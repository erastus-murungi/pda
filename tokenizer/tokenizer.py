import itertools
import re
from typing import Iterator, Optional

from grammar import EOF, Loc, Terminal


def group(*choices):
    return "(" + "|".join(choices) + ")"


def reg_any(*choices):
    return group(*choices) + "*"


def maybe(*choices):
    return group(*choices) + "?"


# Regular expressions used to parse numbers
Hexnumber = r"0[xX](?:_?[0-9a-fA-F])+"
Binnumber = r"0[bB](?:_?[01])+"
Octnumber = r"0[oO](?:_?[0-7])+"
Decnumber = r"(?:0(?:_?0)*|[1-9](?:_?[0-9])*)"
Intnumber = group(Hexnumber, Binnumber, Octnumber, Decnumber)
Exponent = r"[eE][-+]?[0-9](?:_?[0-9])*"
Pointfloat = group(
    r"[0-9](?:_?[0-9])*\.(?:[0-9](?:_?[0-9])*)?", r"\.[0-9](?:_?[0-9])*"
) + maybe(Exponent)
Expfloat = r"[0-9](?:_?[0-9])*" + Exponent
Floatnumber = group(Pointfloat, Expfloat)
Imagnumber = group(r"[0-9](?:_?[0-9])*[jJ]", Floatnumber + r"[jJ]")


class Tokenizer:
    def __init__(
        self, code: str, named_tokens: dict[str, str], filename: str = "(void)"
    ):
        self._filename = filename
        self._named_tokens = named_tokens
        self._code = code + "\n"
        self._linenum = 0
        self._column = 0
        self._code_offset = 0
        self._token_iterable = self._tokenize()

    def _to_next_char(self):
        self._code_offset += 1
        self._column += 1

    def _skip_n_chars(self, n):
        self._code_offset += n
        self._column += n

    def _match_number(self, number_regex: str) -> Optional[tuple[str, str]]:
        match = re.match("^" + number_regex, self._code[self._code_offset :])
        token_type = None
        lexeme = ""
        if match is not None:
            lexeme, token_type = (
                match.group(0),
                "float"
                if number_regex == Floatnumber
                else "integer"
                if number_regex == Intnumber
                else None,
            )
        if token_type is None:
            return None
        else:
            return lexeme, token_type

    def _match_number_or_unknown(self, pos) -> Terminal:
        ret = (
            self._match_number(Imagnumber)
            or self._match_number(Floatnumber)
            or self._match_number(Intnumber)
        )
        if ret is None:
            # no token found
            word_match = re.match(r"\b\w+\b", self._remaining_code())
            if word_match is not None and len(word_match.group(0)) > 1:
                word = word_match.group(0).strip()
                lexeme, ret_type = word, "word"
            else:
                lexeme, ret_type = self._current_char(), "char"
            self._skip_n_chars(len(lexeme) - 1)
            return Terminal(ret_type, lexeme, pos)

        lexeme, ret_type = ret
        self._skip_n_chars(len(lexeme) - 1)
        return Terminal(ret_type, lexeme, pos)

    def _current_char(self):
        return self._code[self._code_offset]

    def _remaining_code(self):
        return self._code[self._code_offset :]

    def _tokenize(self) -> Iterator[Terminal]:
        named_tokens = list(
            sorted(
                self._named_tokens.items(), key=lambda item: len(item[0]), reverse=True
            )
        )
        while self._code_offset < len(self._code):
            token_location = Loc(
                self._filename, self._linenum, self._column, self._code_offset
            )
            # greedy attempt
            for matching, identifier in named_tokens:
                if self._remaining_code().startswith(matching):
                    # this is a keyword
                    self._skip_n_chars(len(matching) - 1)
                    token = Terminal(identifier, matching, token_location)
                    break
            else:
                # we try to match whitespace while avoiding NEWLINES because we
                # are using NEWLINES to split lines in our program
                if self._current_char() != "\n" and self._current_char().isspace():
                    token = Terminal("whitespace", self._current_char(), token_location)
                elif self._current_char() == "#":
                    token = self.handle_comment()
                elif self._current_char() == "\n":
                    token = Terminal.from_token_type("newline", token_location)
                    self._linenum += 1
                    # we set column to -1 because it will be incremented to 0 after the token has been yielded
                    self._column = -1
                else:
                    token = self._match_number_or_unknown(token_location)

            yield token
            self._to_next_char()

        # we must always end our stream of tokens with an EOF token
        yield EOF

    def handle_comment(self):
        end_comment_pos = self._remaining_code().index("\n")
        if end_comment_pos == -1:
            raise ValueError()
        comment = self._remaining_code()[:end_comment_pos]
        token = Terminal(
            "comment",
            comment,
            Loc(
                self._filename,
                self._linenum,
                self._column,
                self._code_offset,
            ),
        )
        self._skip_n_chars(len(comment))
        self._linenum += 1
        # we set column to -1 because it will be incremented to 0 after the token has been yielded
        self._column = -1
        return token

    def get_tokens(self) -> Iterator[Terminal]:
        """
        :return: an iterator over the tokens
        """
        t1, t2 = itertools.tee(self._token_iterable)
        self._token_iterable = t1
        return t2

    def get_tokens_no_whitespace(self):
        return [
            token
            for token in self.get_tokens()
            if not (
                token.token_type
                in (
                    "whitespace",
                    "newline",
                    "comment",
                )
            )
        ]