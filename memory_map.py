from tokenizer import Token, TokenType, get_token_type_name
from enum import Enum
from onebpc import INSTRUCTIONS


class NoteType(Enum):
    ERROR = 1
    WARNING = 2
    COMMENT = 3
    INFO = 4


class Memory_Map:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.map: list[list[Token]] = []
        self.binary: list[str] = []
        self.labels: dict[str, int] = {}
        self.notes: list[tuple[int, int, NoteType, str]] = []

        self._process_tokens()

        self._convert_to_binary()

    def _process_tokens(self):
        # This function processes the list of tokens and builds the memory map.
        # Initialize memory map and labels.
        self.map = []
        self.labels = {}

        # Index in self.tokens
        i = 0
        # Whether the current code is reachable
        # Used for warnings about unreachable code and
        # raw data that might be misinterpreted as code
        is_reachable = True

        while i < len(self.tokens):
            # The address of the previous and next memory word, used for notes
            prev_addr = len(self.map) - 1 if self.map else 0
            next_addr = len(self.map)

            token = self.tokens[i]

            # If the token is a comment or info, add it to the notes and
            # skip adding it to the memory map.
            if token.type == TokenType.COMMENT:
                self.notes.append((prev_addr, token.line_nr,
                                   NoteType.COMMENT, token.value))
                i += 1
                continue
            elif token.type == TokenType.INFO:
                self.notes.append((prev_addr, token.line_nr,
                                   NoteType.INFO, token.value))
                i += 1
                continue

            # If the token is an error, convert it to a note and add a halt
            # instruction to the memory map to minimize impact on
            # memory layout.
            elif token.type == TokenType.ERR:
                self.notes.append((next_addr, token.line_nr,
                                   NoteType.ERROR, token.value))
                halt_token = Token(TokenType.CMD, "halt", token.line_nr,
                                   token.src_text, token.note)
                self.map.append([halt_token])
                i += 1
                continue

            # If the token is a label, record its address
            elif token.type == TokenType.LABEL:
                label_name = token.value
                if label_name in self.labels:
                    self.notes.append((
                        next_addr, token.line_nr,
                        NoteType.ERROR,
                        f"Duplicate label '{label_name}'"
                    ))
                else:
                    self.labels[label_name] = next_addr
                is_reachable = True
                i += 1
                continue

            # If the token is raw binary data, add it to the map. Also warn
            # if the code is reachable, as then it might be misinterpreted
            # as instructions.
            elif token.type == TokenType.BIN:
                self.map.append([token])
                if is_reachable:
                    self.notes.append((
                        next_addr, token.line_nr,
                        NoteType.WARNING,
                        "You put raw data where it might be read as "
                        "instructions. You might have given an argument to an "
                        "instruction that doesn't expect one, or put raw data "
                        "right after a label or at the start of the program."
                    ))
                i += 1
                continue

            # Now handle instructions
            elif token.type == TokenType.CMD:
                if not is_reachable:
                    self.notes.append((
                        next_addr, token.line_nr,
                        NoteType.WARNING,
                        "Unreachable code. This code cannot be reached "
                        "during execution because it comes after a halt or "
                        "unconditional jump, and no label points to it."
                    ))
                    # Only warn once, reset reachability after one warning.
                    is_reachable = True

                # Find the instruction data (opcode, operands, etc) based on
                # the command name given by the user.
                instruction = None
                for instr in INSTRUCTIONS:
                    if token.value in instr.names:
                        instruction = instr
                        break

                # Warn if the instruction is unknown. Add the instruction as
                # an error token anyway to minimize the impact on the size of
                # the memory map. This is based on the assumption that the user
                # made a typo in the instruction name, instead of completely
                # writing something that looks like an instruction where none
                # was intended.
                if instruction is None:
                    self.notes.append((
                        next_addr, token.line_nr,
                        NoteType.ERROR,
                        f"Unknown instruction '{token.value}'"
                    ))
                    i += 1
                    error_token = Token(
                        TokenType.ERR,
                        f"Unknown instruction '{token.value}'",
                        token.line_nr, token.src_text
                    )
                    self.map.append([error_token])
                    continue

                # We are now sure the instruction is valid, so we add it to
                # the memory map and increment i.
                self.map.append([token])
                i += 1

                # Update reachability based on instruction type
                if instruction.names[0] in ["halt", "jump"]:
                    is_reachable = False

                # Now handle operands if the instruction expects them
                if instruction.operands is None:
                    continue

                # If the instruction expects an operand, but the instruction
                # token was the last token, throw an error and continue.
                if i >= len(self.tokens):
                    self.notes.append((
                        next_addr, token.line_nr,
                        NoteType.ERROR,
                        f"Instruction '{token.value}' expects an "
                        "operand, but it was the end of the file."
                    ))
                    continue

                # We now know the current instruction expects an operand, and
                # that there is a token after the instruction.
                operand_token = self.tokens[i]

                if operand_token.type == TokenType.ERR:
                    self.notes.append((
                        next_addr, operand_token.line_nr,
                        NoteType.ERROR,
                        f"Operand for instruction '{token.value}' has an "
                        f"error: {operand_token.value}" +
                        (" Note: " + operand_token.note
                         if operand_token.note else "")
                    ))
                    # If the expected operand is not a label reference, convert
                    # the operand to a zero binary token to minimize impact on
                    # memory layout.
                    if TokenType.LABREF not in instruction.operands:
                        operand_token = Token(TokenType.BIN, "0",
                                              operand_token.line_nr,
                                              operand_token.src_text)
                    else:
                        # If the expected operand is a label reference,
                        # it is not possible to continue meaningfully, so we
                        # ignore the operand and move on.
                        i += 1
                        continue

                # If the token is not of the expected type, throw an error.
                # Try to add the operand anyway to minimize impact on memory
                # layout, and allow users to try weird constructs.
                if operand_token.type not in instruction.operands:
                    self.notes.append((
                        next_addr, operand_token.line_nr,
                        NoteType.ERROR,
                        f"Invalid operand for instruction "
                        f"'{token.value}': expected one of "
                        f"['{"', '".join([get_token_type_name(t)
                                          for t in instruction.operands])}'], "
                        f"got '{get_token_type_name(operand_token.type)}' "
                        f"with value '{operand_token.value}'." +
                        (" Note: " + operand_token.note
                         if operand_token.note else "")
                    ))
                    if TokenType.LABREF in instruction.operands:
                        # If the instruction expects a label reference, put the
                        # operand on its own memory word. This is useful for
                        # when the user wants to manually set addresses.
                        self.map.append([operand_token])
                    else:
                        self.map[-1].append(operand_token)
                    i += 1
                    continue
                # Label references get their own memory word, all their
                # instructions expect the value on the next word instead
                # of combined on the same word.
                if operand_token.type == TokenType.LABREF:
                    self.map.append([operand_token])
                else:
                    self.map[-1].append(operand_token)
                i += 1
            else:
                # Unexpected token type, throw an error. Should not happen.
                self.notes.append((
                    prev_addr, token.line_nr,
                    NoteType.ERROR,
                    f"Unexpected token type {get_token_type_name(token.type)} "
                    f"with value '{token.value}'." +
                    (" Note: " + token.note if token.note else "")
                ))
                i += 1

    def _convert_to_binary(self):
        # This function converts the memory mapped tokens to binary strings.
        self.binary = [
            self._convert_tokens_to_word(tokens, address)
            for address, tokens in enumerate(self.map)
        ]

    def _convert_tokens_to_word(self, tokens: list[Token], address: int) -> \
            str:
        # This function converts a list of tokens for a single memory word
        # to a binary string.
        WORD_LENGTH = 10

        # If there are no tokens, return a word of all zeros.
        if not tokens:
            return "0" * WORD_LENGTH

        # Because instructions never take more than 1 operand, we can error
        # check based on the number of tokens. This should have been checked
        # for already during mapping.
        if len(tokens) > 2:
            self.notes.append((
                address, tokens[0].line_nr,
                NoteType.ERROR,
                "Internal error: Too many tokens to fit in one memory word."
            ))
            return "0" * WORD_LENGTH

        # Now convert based on the type of the first token
        first_token = tokens[0]

        # If the first token is an error, just return a word of zeros.
        # This word was already marked as error by the mapper, but the
        # mapper decided it still wanted this address to be filled.
        if first_token.type == TokenType.ERR:
            return "0" * WORD_LENGTH

        # If the first token is binary data, use it directly.
        elif first_token.type == TokenType.BIN:
            if len(tokens) != 1:
                self.notes.append((
                    address, first_token.line_nr,
                    NoteType.ERROR,
                    "Internal error: Extra tokens found after binary data."
                ))
            bin_value = first_token.value
            if len(bin_value) > WORD_LENGTH:
                self.notes.append((
                    address, first_token.line_nr,
                    NoteType.ERROR,
                    f"Error: Binary value '{bin_value}' exceeds "
                    f"word length of {WORD_LENGTH}."
                ))
                return bin_value[:WORD_LENGTH]
            return bin_value.zfill(WORD_LENGTH)

        # If the token is a label reference, convert it to the address.
        # We couldn't do this earlier because the address could have been
        # later in the code. Now that all labels are known, we can convert it.
        elif first_token.type == TokenType.LABREF:
            if len(tokens) != 1:
                self.notes.append((
                    address, first_token.line_nr,
                    NoteType.ERROR,
                    "Internal error: Extra tokens found after label reference."
                ))
            label_name = tokens[0].value
            if label_name not in self.labels:
                self.notes.append((
                    address, first_token.line_nr,
                    NoteType.ERROR,
                    f"Error: Undefined label reference '{label_name}'."
                ))
                return "0" * WORD_LENGTH
            bin_address = bin(self.labels[label_name])[2:]  # Remove 0b prefix
            self.notes.append((
                address, first_token.line_nr,
                NoteType.INFO,
                f"Points to label '{label_name}'"))
            if len(bin_address) > WORD_LENGTH:
                self.notes.append((
                    address, first_token.line_nr,
                    NoteType.ERROR,
                    f"Error: Address of label '{label_name}' "
                    f"exceeds word length of {WORD_LENGTH}."
                ))
                return bin_address[:WORD_LENGTH]
            return bin_address.zfill(WORD_LENGTH)

        # Now handle instructions
        elif first_token.type == TokenType.CMD:
            # First find the instruction data for the opcode
            instruction = None
            for instr in INSTRUCTIONS:
                if first_token.value in instr.names:
                    instruction = instr
                    break
            if instruction is None:
                self.notes.append((
                    address, first_token.line_nr,
                    NoteType.ERROR,
                    f"Internal error: Unknown instruction "
                    f"'{first_token.value}' during binary conversion."
                ))
                return "0" * WORD_LENGTH
            opcode = instruction.opcode

            # The mapper already packaged any needed operands correctly.
            if len(tokens) == 1:
                if len(opcode) > WORD_LENGTH:
                    self.notes.append((
                        address, first_token.line_nr,
                        NoteType.ERROR,
                        f"Error: Opcode '{opcode}' exceeds word length "
                        f"of {WORD_LENGTH}."
                    ))
                    return opcode[:WORD_LENGTH]
                return opcode.zfill(WORD_LENGTH)
            # We now know that len(tokens) == 2:
            # There is an operand, and we just need to append it to the
            # opcode. Any further checking was already done by the mapper.
            # Non-label operands are always numbers that have already
            # been converted to binary.
            operand_token = tokens[1]
            operand_value = operand_token.value
            if operand_token.type != TokenType.BIN:
                self.notes.append((
                    address, operand_token.line_nr,
                    NoteType.ERROR,
                    f"Internal error: Unexpected operand type "
                    f"{operand_token.type} during binary conversion."
                ))
                operand_value = ""
            full_value = opcode + operand_value.zfill(
                WORD_LENGTH - len(opcode))
            if len(full_value) > WORD_LENGTH:
                self.notes.append((
                    address, first_token.line_nr,
                    NoteType.ERROR,
                    f"Error: Combined opcode and operand "
                    f"'{full_value}' exceeds word length of "
                    f"{WORD_LENGTH}."
                ))
                return full_value[:WORD_LENGTH]
            return full_value.zfill(WORD_LENGTH)
        # If we reach here, the token type is unexpected.
        else:
            self.notes.append((
                address, first_token.line_nr,
                NoteType.ERROR,
                f"Internal error: Unexpected token type "
                f"{first_token.type} during binary conversion."
            ))
            return "0" * WORD_LENGTH
