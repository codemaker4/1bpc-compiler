from macro import Macro
from tokenizer import Token, TokenType, get_token_value_as_int

MACROS: list[Macro] = []


def define(tokens: list[Token], context: dict) -> list[Token]:
    macro_name_token = tokens[1]
    macro_body_token = tokens[2]

    macro_name = macro_name_token.value

    if "defines" not in context:
        context["defines"] = {}

    if macro_name in context["defines"]:
        src_text = " ".join(t.src_text for t in tokens)
        return [Token(TokenType.ERR,
                      f"Macro '{macro_name}' is already defined.",
                      tokens[0].line_nr,
                      src_text)]

    context["defines"][macro_name] = Token(
        macro_body_token.type, macro_body_token.value,
        macro_body_token.line_nr, macro_body_token.src_text,
        macro_body_token.note)
    return []


MACROS.append(Macro("define", [TokenType.LABEL, TokenType.BIN],
                    define))
MACROS.append(Macro("define", [TokenType.LABEL, TokenType.DECIMAL],
                    define))
MACROS.append(Macro("define", [TokenType.LABEL, TokenType.HEXADECIMAL],
                    define))
MACROS.append(Macro("define", [TokenType.LABEL, TokenType.CMD],
                    define))


def use(tokens: list[Token], context: dict) -> list[Token]:
    macro_name_token = tokens[1]
    macro_name = macro_name_token.value

    if "defines" not in context or \
            macro_name not in context["defines"]:
        src_text = " ".join(t.src_text for t in tokens)
        return [Token(TokenType.ERR,
                      f"Macro '{macro_name}' is not defined.",
                      macro_name_token.line_nr,
                      src_text)]

    defined_token = context["defines"][macro_name]

    src_text = " ".join(t.src_text for t in tokens)

    return [Token(defined_token.type, defined_token.value,
                  macro_name_token.line_nr,
                  src_text,
                  macro_name_token.note)]


MACROS.append(Macro("use", [TokenType.LABREF], use))


def malloc(tokens: list[Token], context: dict) -> list[Token]:
    label_token = tokens[1]
    size_token = tokens[2]

    size = get_token_value_as_int(size_token)

    if "mallocs" not in context:
        context["mallocs"] = {"next_address": 0, "allocations": {}}

    address = context["mallocs"]["next_address"]

    new_next_address = address + size

    if new_next_address >= 256:
        new_next_address = 255

    context["mallocs"]["allocations"][label_token.value] = \
        {"address": address,
         "size": size}
    context["mallocs"]["next_address"] = new_next_address

    if new_next_address >= 256 - 16:
        src_text = " ".join(t.src_text for t in tokens)
        return [Token(TokenType.ERR,
                      f"Not enough memory to allocate {size} bytes "
                      f"for '{label_token.value}'.",
                      size_token.line_nr,
                      src_text)]

    return [Token(TokenType.INFO,
                  f"'{label_token.value}' is allocated to [{address}: "
                  f"{address + size - 1}] ({size} bits)",
                  tokens[0].line_nr,
                  " ".join(t.src_text for t in tokens))]


MACROS.append(Macro("malloc", [TokenType.LABEL, TokenType.BIN],
                    malloc))
MACROS.append(Macro("malloc", [TokenType.LABEL, TokenType.DECIMAL],
                    malloc))
MACROS.append(Macro("malloc", [TokenType.LABEL, TokenType.HEXADECIMAL],
                    malloc))


def at_math(tokens: list[Token], context: dict) -> list[Token]:
    math_token = tokens[1]
    labref_tokens = tokens[2:]

    if labref_tokens[-1].type != TokenType.LABREF:
        operation_length_token = labref_tokens.pop()
        operation_length = get_token_value_as_int(operation_length_token)
    else:
        operation_length = None
        first_alloc = None
        first_alloc_name = None
        for t in labref_tokens:
            if "mallocs" in context and \
                    t.value in context["mallocs"]["allocations"]:
                alloc = context["mallocs"]["allocations"][t.value]
                if operation_length is None or first_alloc is None:
                    operation_length = alloc["size"]
                    first_alloc = alloc
                    first_alloc_name = t.value
                elif operation_length != alloc["size"]:
                    src_text = " ".join(t.src_text for t in tokens)
                    return [Token(TokenType.ERR,
                                  f"Size mismatch in 'at <math>' macro: "
                                  f"'{first_alloc_name}' has size "
                                  f"{first_alloc['size']}, but "
                                  f"'{t.value}' has size {alloc['size']}. "
                                  f"If this is intentional, please specify "
                                  f"the operation length explicitly by using "
                                  f"'{src_text} <length>'.",
                                  t.line_nr,
                                  src_text)]

        if operation_length is None:
            src_text = " ".join(t.src_text for t in tokens)
            return [Token(TokenType.ERR,
                          "Could not determine operation length in "
                          "'at <math>' macro, because none of the provided "
                          "labels are allocated.",
                          tokens[0].line_nr,
                          src_text)]

        operation_length -= 1  # Adjust for 0-based lengths of math operations
        operation_length_token = Token(
            TokenType.BIN, bin(operation_length)[2:],  # Remove '0b' prefix
            tokens[-1].line_nr,
            f"{operation_length}",
            "Operation length determined by at math macro from alloc sizes")

    return_tokens: list[Token] = []

    def make_at_token(labref_token: Token) -> Token:
        return Token(TokenType.CMD, "at",
                     tokens[0].line_nr,  # Line numbers must be consecutive
                     "at",
                     (", " if labref_token.note else "") +
                     "from 'at <math>' macro")

    math_operation = math_token.value.lower()

    # Some operations only have a source operand and no destination operand
    if math_operation in ["checksum", "bc"]:
        if len(labref_tokens) != 1:
            src_text = " ".join(t.src_text for t in tokens)
            return [Token(TokenType.ERR,
                          f"Incorrect number of operands for "
                          f"'{math_operation}' in 'at <math>' macro. This "
                          f"operation only takes one input, so provide "
                          f"only the source label.",
                          tokens[0].line_nr,
                          src_text)]
        return_tokens.append(Token(TokenType.CMD, "set_a",
                                   tokens[0].line_nr,
                                   "set_a"))
        return_tokens.append(make_at_token(labref_tokens[0]))
        # Line numbers must be consecutive
        labref_tokens[0].line_nr = tokens[0].line_nr
        return_tokens.append(labref_tokens[0])
    # Some operations have only one source operand and a destination operand
    elif math_operation in ["move_data", "md",
                            "invert", "bi"]:
        if len(labref_tokens) > 2:
            src_text = " ".join(t.src_text for t in tokens)
            return [Token(TokenType.ERR,
                          f"Too many operands for '{math_operation}' "
                          f"in 'at <math>' macro. This operation only "
                          f"takes one input, so either give the source and "
                          f"destination label, or only the destination label.",
                          tokens[0].line_nr,
                          src_text)]
        if len(labref_tokens) == 2:
            return_tokens.append(Token(TokenType.CMD, "set_a",
                                       tokens[0].line_nr,
                                       "set_a"))
            return_tokens.append(make_at_token(labref_tokens[0]))
            # Line numbers must be consecutive
            labref_tokens[0].line_nr = tokens[0].line_nr
            return_tokens.append(labref_tokens[0])
        return_tokens.append(Token(TokenType.CMD, "set_c",
                                   tokens[0].line_nr,
                                   "set_c"))
        return_tokens.append(make_at_token(labref_tokens[-1]))
        # Line numbers must be consecutive
        labref_tokens[-1].line_nr = tokens[0].line_nr
        return_tokens.append(labref_tokens[-1])
    # Operations that have two source operands and a destination operand
    elif math_operation in ["add", "+",
                            "subtract", "-",
                            "and", "ba",
                            "or", "bo",
                            "xor", "bx",
                            "nand", "bna",
                            "nor", "bno",
                            "nxor", "bnx"]:
        if len(labref_tokens) in [2, 3]:
            return_tokens.append(Token(TokenType.CMD, "set_a",
                                       tokens[0].line_nr,
                                       "set_a"))
            return_tokens.append(make_at_token(labref_tokens[0]))
            # Line numbers must be consecutive
            labref_tokens[0].line_nr = tokens[0].line_nr
            return_tokens.append(labref_tokens[0])
            return_tokens.append(Token(TokenType.CMD, "set_b",
                                       tokens[0].line_nr,
                                       "set_b"))
            return_tokens.append(make_at_token(labref_tokens[1]))
            # Line numbers must be consecutive
            labref_tokens[1].line_nr = tokens[0].line_nr
            return_tokens.append(labref_tokens[1])
        if len(labref_tokens) in [1, 3]:
            return_tokens.append(Token(TokenType.CMD, "set_c",
                                       tokens[0].line_nr,
                                       "set_c"))
            return_tokens.append(make_at_token(labref_tokens[-1]))
            # Line numbers must be consecutive
            labref_tokens[-1].line_nr = tokens[0].line_nr
            return_tokens.append(labref_tokens[-1])
    else:
        src_text = " ".join(t.src_text for t in tokens)
        return [Token(TokenType.ERR,
                      f"Unknown math operation '{math_operation}' "
                      f"in 'at <math>' macro.",
                      math_token.line_nr,
                      src_text)]

    if operation_length > 15:
        operation_length_token.note = (
            (operation_length_token.note + ", ")
            if operation_length_token.note else ""
        ) + "Split operation length from 'at <math>' macro."

    while operation_length > 15:
        return_tokens.append(math_token)
        return_tokens.append(Token(TokenType.BIN, "1111",
                                   math_token.line_nr,
                                   "15",
                                   "Split operation length from 'at <math>' "
                                   "macro."))
        operation_length -= 16
        operation_length_token.type = TokenType.BIN
        operation_length_token.value = bin(operation_length)[2:]
        operation_length_token.src_text = f"{operation_length}"
    return_tokens.append(math_token)
    return_tokens.append(operation_length_token)

    print("DEBUG: at_math returning tokens:", return_tokens)

    return return_tokens


for i in [3, 2, 1]:
    for j in [TokenType.BIN, TokenType.DECIMAL, TokenType.HEXADECIMAL]:
        operands = [TokenType.CMD] + [TokenType.LABREF] * i + [j]
        MACROS.append(Macro("at", operands, at_math))
    MACROS.append(Macro("at", [TokenType.CMD] + [TokenType.LABREF] * i,
                        at_math))


def at(tokens: list[Token], context: dict) -> list[Token]:
    label_token = tokens[1]

    if "mallocs" not in context or \
            label_token.value not in context["mallocs"]["allocations"]:
        src_text = " ".join(t.src_text for t in tokens)
        return [Token(TokenType.ERR,
                      f"Memory label '{label_token.value}' is not allocated.",
                      label_token.line_nr,
                      src_text)]

    address = context["mallocs"]["allocations"][label_token.value]["address"]

    src_text = " ".join(t.src_text for t in tokens)

    return [Token(TokenType.BIN, bin(address)[2:],  # Remove '0b' prefix
                  label_token.line_nr,
                  src_text,
                  f"{", ".join(t.note for t in tokens if t.note)}")]


MACROS.append(Macro("at", [TokenType.LABREF], at))


def load_byte(tokens: list[Token], context: dict) -> list[Token]:
    byte_value_token = tokens[1]
    byte_value = get_token_value_as_int(byte_value_token)

    if byte_value < 0 or byte_value > 255:
        src_text = " ".join(t.src_text for t in tokens)
        return [Token(TokenType.ERR,
                      f"Byte value {byte_value} out of range (0-255).",
                      byte_value_token.line_nr,
                      src_text)]

    binary_value = bin(byte_value)[2:]  # Remove '0b' prefix
    binary_value = binary_value.zfill(8)  # Ensure it's 8 bits

    instruction_name = "load" if "_" in tokens[0].src_text else "l"

    return [Token(TokenType.CMD, instruction_name,
                  tokens[0].line_nr,
                  instruction_name,
                  byte_value_token.note),
            Token(TokenType.BIN, binary_value[4:],  # Lower 4 bits
                  byte_value_token.line_nr,
                  byte_value_token.src_text,
                  f"lower 4 bits of byte {byte_value}"),
            Token(TokenType.CMD, instruction_name,
                  byte_value_token.line_nr,
                  instruction_name),
            Token(TokenType.BIN, binary_value[:4],  # Upper 4 bits
                  byte_value_token.line_nr,
                  byte_value_token.src_text,
                  f"upper 4 bits of byte {byte_value}")]


MACROS.append(Macro("load_byte", [TokenType.BIN], load_byte))
MACROS.append(Macro("load_byte", [TokenType.DECIMAL], load_byte))
MACROS.append(Macro("load_byte", [TokenType.HEXADECIMAL], load_byte))
MACROS.append(Macro("lb", [TokenType.BIN], load_byte))
MACROS.append(Macro("lb", [TokenType.DECIMAL], load_byte))
MACROS.append(Macro("lb", [TokenType.HEXADECIMAL], load_byte))


def load_double(tokens: list[Token], context: dict) -> list[Token]:
    double_value_token = tokens[1]
    double_value = get_token_value_as_int(double_value_token)

    if double_value < 0 or double_value > 65535:
        src_text = " ".join(t.src_text for t in tokens)
        return [Token(TokenType.ERR,
                      f"Double byte value {double_value} out of range "
                      f"(0-65535).",
                      double_value_token.line_nr,
                      src_text)]

    binary_value = bin(double_value)[2:]  # Remove '0b' prefix
    binary_value = binary_value.zfill(16)  # Ensure it's 16 bits

    nibbles = [Token(TokenType.BIN, binary_value[i:i + 4],
                     double_value_token.line_nr,
                     double_value_token.src_text + f"[{i}:{i + 4}]",
                     f"nibble {i // 4} of double byte "
                     f"{double_value_token.src_text}")
               for i in range(12, -4, -4)]

    return_tokens: list[Token] = []

    instruction_name = "load" if "_" in tokens[0].src_text else "l"

    for nibble in nibbles:
        return_tokens.append(Token(TokenType.CMD, instruction_name,
                                   nibble.line_nr,
                                   instruction_name))
        return_tokens.append(nibble)
    return return_tokens


MACROS.append(Macro("load_double", [TokenType.BIN], load_double))
MACROS.append(Macro("load_double", [TokenType.DECIMAL], load_double))
MACROS.append(Macro("load_double", [TokenType.HEXADECIMAL], load_double))
MACROS.append(Macro("ld", [TokenType.BIN], load_double))
MACROS.append(Macro("ld", [TokenType.DECIMAL], load_double))
MACROS.append(Macro("ld", [TokenType.HEXADECIMAL], load_double))


def do_while_do(tokens: list[Token], context: dict) -> list[Token]:
    label_token = tokens[1]
    return [Token(TokenType.LABEL, label_token.value,
                  label_token.line_nr, "do " + label_token.src_text)]


MACROS.append(Macro("do", [], lambda tokens, context: []))


def do_while_while(tokens: list[Token], context: dict) -> list[Token]:
    condition_token = tokens[1]
    label_token = tokens[2]

    conditions: dict[str, str] = {
        "a0": "ja0",
        "a_0": "jump_if_a_0",
        "a1": "ja1",
        "a_1": "jump_if_a_1",
        "c0": "jc0",
        "c_0": "jump_if_carry_0",
        "c1": "jc1",
        "c_1": "jump_if_carry_1",
        "t": "jt",
        "triggered": "jump_if_triggered",
    }

    if condition_token.value not in conditions:
        src_text = " ".join(t.src_text for t in tokens)
        return [Token(TokenType.ERR,
                      f"Unknown condition '{condition_token.value}' "
                      f"in 'while' macro. Please use one of: "
                      f"{', '.join(conditions.keys())}.",
                      condition_token.line_nr,
                      src_text)]

    jump_instruction = conditions[condition_token.value]

    src_text = " ".join(t.src_text for t in tokens[0:1])

    return [Token(TokenType.CMD, jump_instruction,
                  tokens[0].line_nr,
                  src_text,
                  tokens[0].note),
            Token(TokenType.LABREF, label_token.value,
                  label_token.line_nr,
                  label_token.src_text,
                  label_token.note)]


MACROS.append(Macro("while", [TokenType.CMD, TokenType.LABREF],
                    do_while_while))


def do_while_until(tokens: list[Token], context: dict) -> list[Token]:
    condition_token = tokens[1]
    label_token = tokens[2]

    conditions: dict[str, str] = {
        "t": "jt",
        "triggered": "jump_if_triggered",
    }

    if condition_token.value not in conditions:
        src_text = " ".join(t.src_text for t in tokens)
        return [Token(TokenType.ERR,
                      f"Unknown condition '{condition_token.value}' "
                      f"in 'until' macro. Please use one of: "
                      f"{', '.join(conditions.keys())}.",
                      condition_token.line_nr,
                      src_text)]

    jump_instruction = conditions[condition_token.value]
    back_jump_instruction = "jump" if len(condition_token.value) < 3 else "ji"

    end_label_name = f"__{label_token.value}_end"

    return [Token(TokenType.CMD, jump_instruction,
                  tokens[0].line_nr,
                  tokens[0].src_text + " " + condition_token.src_text,
                  tokens[0].note),
            Token(TokenType.LABREF, end_label_name,
                  tokens[0].line_nr,
                  f":{end_label_name}",
                  f"end label for until loop '{label_token.value}'"),
            Token(TokenType.CMD, back_jump_instruction,
                  label_token.line_nr,
                  label_token.src_text,
                  label_token.note),
            Token(TokenType.LABREF, label_token.value,
                  label_token.line_nr,
                  label_token.src_text,
                  label_token.note),
            Token(TokenType.LABEL, end_label_name,
                  label_token.line_nr,
                  f":{end_label_name}",
                  f"end label for until loop '{label_token.value}'")]


MACROS.append(Macro("until", [TokenType.CMD, TokenType.LABREF],
                    do_while_until))
