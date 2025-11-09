from tokenizer import Token, TokenType
from typing import Callable


class Macro:
    def __init__(self, name: str, operands: list[TokenType],
                 process: Callable[[list[Token], dict], list[Token]]):
        self.name = name
        self.operands = operands
        # Processes the given list of tokens according to this macro's
        # definition, returning a new list of tokens.
        # The dictionary can be used to store and retrieve context information
        # during preprocessing.
        self.process = process

    # Returns the total number of tokens this macro consumes
    def __len__(self) -> int:
        return 1 + len(self.operands)

    # Returns True if the given token is an instruction token matching this
    # macro's name
    def token_matches_name(self, token: Token) -> bool:
        return token.type == TokenType.CMD and token.value == self.name

    # Returns True if the given list of tokens matches this macro definition
    def tokens_match_macro(self, tokens: list[Token]) -> bool:
        if len(tokens) < len(self):
            return False
        if not self.token_matches_name(tokens[0]):
            return False
        for i, operand_type in enumerate(self.operands):
            if tokens[i + 1].type != operand_type:
                return False
        return True

    # Consumes tokens from the start of the given list according to this
    # macro's definition, returning a tuple of
    # (consumed tokens, remaining tokens)
    def consume_tokens(self, tokens: list[Token]) -> \
            tuple[list[Token], list[Token]]:
        if not self.tokens_match_macro(tokens):
            raise ValueError("Token prefix does not match macro definition.")
        return tokens[:len(self)], tokens[len(self):]
