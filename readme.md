Compiler for the 1bpc architecture.

# Usage
basic:

`python main.py source.txt`

`python main.py source.txt output.txt`

add lots nicely formatted debug info to the output file

`python main.py --show-labels --note-level info --word-wrap-limit 80 --add-address-numbers --show-token-src --add-token-notes --use-hashtags source.txt output.txt`

automatically recompile when the source file changes, and keep all the notes for each address on the same line

`python main.py --show-labels --note-level info --add-address-numbers --show-token-src --add-token-notes --use-hashtags --auto-recompile source.txt output.txt`

format the extra info in a computer-readable format

`python main.py --show-labels --note-level info --add-address-numbers --show-token-src --add-token-notes source.txt output.txt`

## arguments

- `source.txt`: path to the source file to compile.
- `output.txt`: path to the output file to write the memory map to. If not specified, defaults to `compiled.txt`.

## options
- `--show-labels`: show labels in the output memory map. If `--spread-notes` or `--word-wrap-limit` is used, labels will be put on a seperate line before the instruction at that address. Otherwise, they will be put on the same line after the binary code.
- `--note-level [error|warning|comment|info]`: minimum note level to both in the output file and in the terminal. If this is not specified, it will not put any notes in the output file, and only errors and warnings will be printed to the terminal.
- `--spread-notes`: put notes on seperate lines below the instruction they refer to, instead of at the end of the line. This makes the output file longer, but easier to read. Omitting this is recommended for if you want a different program to parse the output file. This option is automatically enabled if `--word-wrap-limit` is used.
- `--word-wrap-limit [number]`: wrap lines with notes that exceed this length. Only applies if (token) notes are being shown. If this option is used, `--spread-notes` is automatically enabled.
- `--add-address-numbers`: add the memory address at the start of each line in the output file.
- `--show-token-src`: show the original source code of each token (piece of source code) in the output file. This is useful for understanding what each binary word was generated from. When used together with `--show-labels`, labels will be shown before the instruction at that address, causing all the active source code to be visible in the output file.
- `--add-token-notes`: show notes attached to tokens in the output file. This is useful for understanding why certain errors or warnings were generated. Note that this won't do anything without `--note-level info`. Token notes are currently only generated when decimal and hexadecimal numbers are converted to binary tokens in preparation for compiling.
- `--use-hashtags`: use `#` for 1s and `-` for 0s in the binary output, instead of `1` and `0`. This makes the binary code easier to read for humans.
- `--auto-recompile`: automatically recompile the source file whenever it is changed. Note that this will not terminate on its own, you have to manually stop the program (e.g. with Ctrl+C).

# How it works
- First, main.py interperets your command arguments and reads the source file.
- Then `compile_source()` is called:
    - This uses `tokenizer.py` to parse and tokenize the input file.
    - This token list is then given to `preprocessor.py` which handles macros and variables.
    - Now all tokens are valid 1bpc machine code. To help the next step, decimal and hexadecimal number tokens are converted to binary tokens.
    - Then it gives the token list to `memory_map.py` where the girth of the compiler is located.
        - This will first spread the tokens out over the memory map based on the token types and instruction arguments This is also where most user errors are detected
        - Once all tokens are assigned an address on the map, the binary code is generated. This step is seperate because for this we need all labels to have been assigned their address already.
    - This memory map is then nicely formatted by the code in main.py. I admit that this code is a mess, sorry for that.
    - This formatted memory map is then written to the output file, and a summary of the warnings and errors is printed to the terminal.

# Bonus info
- The preprocessor is a terrible name, I should have just called it macro processor.
- The macro processor was mostly built in a single day, and mostly using AI. It works well and it worked first try, but the code is a mess. Forgive me for my sins.
- I made the memory mapper (the girth of the compiler) only handle binary numbers, and processed al decimal and hexadecimal numbers into binary before giving the tokens to the memory mapper. This made the memory mapper code much simpler. When I made the macro processor, for some reason I thought it would be better to give it the original decimal and hexadecimal numbers, but this is completely pointless. You could probably go in the code and swap the order of the macro processor and the decimal/hex to binary conversion step, and it would work just as well, except that a good portion of the macro processor code would go unused.
- This code goes online before the computer it is built for is even finished. If you can somehow reverse engineer the architecture from this code, congratulations: you just earned a nonzero amount of internet points.

# Credits
Architecture and compiler made by CodeMaker_4.
Code partially generated with GitHub Copilot using various models. Sorry for the slop :)
