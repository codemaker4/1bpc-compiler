from enum import Enum
import re


class TokenType(Enum):
    CMD = 1
    BIN = 2
    DECIMAL = 3
    HEXADECIMAL = 4
    LABEL = 5
    LABREF = 6
    COMMENT = 7
    ERR = 8
    INFO = 9


def get_token_type_name(token_type: TokenType) -> str:
    return {
        TokenType.CMD: "Instruction",
        TokenType.BIN: "Binary Number",
        TokenType.DECIMAL: "Decimal Number",
        TokenType.HEXADECIMAL: "Hexadecimal Number",
        TokenType.LABEL: "Label",
        TokenType.LABREF: "Label Reference",
        TokenType.COMMENT: "Comment",
        TokenType.ERR: "Error",
        TokenType.INFO: "Info",
    }[token_type]


class Token:
    def __init__(self, type: TokenType, value: str, line_nr: int,
                 src_text: str, note: str | None = None):
        self.type = type
        self.value = value
        self.line_nr = line_nr
        self.src_text = src_text
        self.note = note

    def __repr__(self):
        return (f'Token(type={self.type}, value="{self.value}", '
                f'line_nr={self.line_nr}, note="{self.note}")')


# Matches commands (consisting of letters, +, -)
_RE_CMD = re.compile(r"^([a-z\+\-_][a-z0-9\+\-_]*)$")
# Matches binary numbers prefixed with %
_RE_BIN = re.compile(r"^%([01]+)$")
# Matches decimal numbers prefixed with nothing
_RE_DECIMAL = re.compile(r"^(\d+)$")
# Matches hexadecimal numbers prefixed with 0x
_RE_HEXADECIMAL = re.compile(r"^0x([0-9a-f]+)$")
# Matches labels ending with :
_RE_LABEL = re.compile(r"^([a-z_][a-z0-9_]*):$")
# Matches label references starting with :
_RE_LABREF = re.compile(r"^:([a-z_][a-z0-9_]*)$")
# Matches comments starting with //, ; or #
_RE_COMMENT = re.compile(r"^(//|;|#)(.*)")


def _tokenize_substring(substring: str, line_nr: int
                        ) -> tuple[Token | None, str]:
    substring = substring.lstrip()

    if substring == "":
        return None, ""

    line = substring.splitlines()[0]
    match_comment = _RE_COMMENT.match(line)
    if match_comment:
        comment_text = match_comment.group(2).strip()
        token = Token(TokenType.COMMENT, comment_text, line_nr, line)
        remaining = substring[len(line):]
        return token, remaining

    tokentext, remainder = (substring.split(maxsplit=1)
                            if ' ' in substring else (substring, ''))
    for regex, token_type in [
        (_RE_CMD, TokenType.CMD),
        (_RE_BIN, TokenType.BIN),
        (_RE_DECIMAL, TokenType.DECIMAL),
        (_RE_HEXADECIMAL, TokenType.HEXADECIMAL),
        (_RE_LABEL, TokenType.LABEL),
        (_RE_LABREF, TokenType.LABREF),
    ]:
        match = regex.match(tokentext)
        if match:
            return (Token(token_type, match.group(1), line_nr, tokentext),
                    remainder)

    return (Token(TokenType.ERR,
                  f"Syntax error: Cannot understand \"{tokentext}\"",
                  line_nr, tokentext),
            remainder)


def tokenize(source_code: str) -> list[Token]:
    tokens: list[Token] = []
    for line_nr, line in enumerate(source_code.splitlines(), start=1):
        substring = line
        while substring:
            token, substring = _tokenize_substring(substring, line_nr)
            if token:
                tokens.append(token)
    return tokens


def convert_token_to_binary(token: Token) -> Token:
    if token.type == TokenType.DECIMAL:
        value = int(token.value)
        binary_value = bin(value)[2:]  # Remove '0b' prefix
        return Token(TokenType.BIN, binary_value, token.line_nr,
                     token.src_text,
                     ((", " + token.note) if token.note else "") +
                     f"converted from decimal: {token.value}")
    elif token.type == TokenType.HEXADECIMAL:
        value = int(token.value, 16)
        binary_value = bin(value)[2:]  # Remove '0b' prefix
        return Token(TokenType.BIN, binary_value, token.line_nr,
                     token.src_text,
                     ((", " + token.note) if token.note else "") +
                     f"converted from hex: 0x{token.value}")
    else:
        return token


def get_token_value_as_int(token: Token) -> int:
    if token.type == TokenType.BIN:
        return int(token.value, 2)
    elif token.type == TokenType.DECIMAL:
        return int(token.value)
    elif token.type == TokenType.HEXADECIMAL:
        return int(token.value, 16)
    raise ValueError(f"Cannot convert token of type {token.type} "
                     f"to integer.")


def convert_numbers_to_binary(tokens: list[Token]) -> list[Token]:
    result: list[Token] = []
    for token in tokens:
        result.append(convert_token_to_binary(token))
    return result


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        print("Usage: python tokenizer.py <input_file> <output_file>")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]

    with open(input_file, 'r') as f:
        source_code = f.read()

    tokens = tokenize(source_code)

    with open(output_file, 'w') as f:
        for token in tokens:
            f.write(repr(token) + '\n')
