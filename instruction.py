from tokenizer import TokenType


class Instruction:
    def __init__(self, opcode: str, names: list[str],
                 operands: list[TokenType] | None = None):
        self.opcode = opcode
        self.names = names
        # Instructions can only have 1 operand, but it can be of multiple types
        # If operands is None, the instruction takes no operands
        self.operands = operands

    def __repr__(self):
        return (f'Instruction(opcode="{self.opcode}", names={self.names}, '
                f'operands={self.operands})')
