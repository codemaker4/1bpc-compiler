from tokenizer import Token, TokenType, get_token_type_name
from onebpc_macros import MACROS


def preprocess_tokens(tokens: list[Token]) -> list[Token]:
    ctx: dict = {}
    for macro in MACROS:
        i = 0
        while i < len(tokens):
            if macro.tokens_match_macro(tokens[i:]):
                consumed, remaining = macro.consume_tokens(tokens[i:])
                new_tokens = macro.process(consumed, ctx)
                tokens = tokens[:i] + new_tokens + remaining
            else:
                i += 1
    macro_names = set(macro.name for macro in MACROS)
    for token in tokens:
        if (token.type == TokenType.CMD and token.value in macro_names):
            argument_options = [f"[{", ".join(
                [get_token_type_name(operand) for operand in macro.operands]
                )}]" for macro in MACROS if macro.name == token.value]
            argument_options = ", or ".join(argument_options)
            token.type = TokenType.ERR
            token.value = f"Macro '{token.value}' usage is incorrect. The " \
                          f"argument options are: {argument_options}."

    return tokens
