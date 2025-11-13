# Compiles programs for the 1bpc architecture.

from tokenizer import tokenize, convert_numbers_to_binary
from memory_map import Memory_Map, NoteType
from preprocessor import preprocess_tokens
from export import export_memory_map
import time


def compile_source(source_code: str) -> Memory_Map:
    print("    Tokenizing source code...")
    tokens = tokenize(source_code)
    print("    Processing macros...")
    tokens = preprocess_tokens(tokens)
    print("    Converting numbers to binary...")
    tokens = convert_numbers_to_binary(tokens)
    print("    Generating memory map...")
    return Memory_Map(tokens)


def word_wrap(text: str, width: int, indent: int = 0) -> str:
    words = text.split(' ')
    if len(words) == 0:
        return text
    lines: list[str] = []
    current_line: str = words[0]

    for word in words[1:]:
        if len(current_line) + len(word) + 1 <= width:
            if current_line:
                current_line += ' '
            current_line += word
        else:
            if current_line:
                lines.append(current_line)
            current_line = ' ' * indent + word

    if current_line:
        lines.append(current_line)

    return '\n'.join(lines)


def get_output(memory_map: Memory_Map,
               show_labels: bool = False,
               note_level: NoteType | None = None,
               spread_notes: bool = False,
               word_wrap_limit: int | None = None,
               add_address_numbers: bool = False,
               show_token_src: bool = False,
               add_token_notes: bool = False,
               use_hashtags: bool = False) -> str:
    # Generate the output from the memory map.

    # The lines of output.
    output: list[str] = []

    # Keep track of the last source code line number processed.
    last_line_number = 0

    # For every word in the memory map, generate output.
    for address, word in enumerate(memory_map.binary):
        # Get the tokens for this address.
        tokens = memory_map.map[address]

        # Find the labels that point to this address.
        labels = []
        if show_labels:
            for label, label_address in memory_map.labels.items():
                if label_address == address:
                    labels.append(label)

        # If we spread the notes over multiple lines, collect notes that
        # were written on lines between actual compiled code, to be placed
        # on their own lines, above the line containing the binary output for
        # the current address.
        skipped_notes = []
        if spread_notes and note_level is not None:
            current_line_number = tokens[0].line_nr
            for note in memory_map.notes:
                note_address, line_nr, note_type, note_text = note
                if note_type.value > note_level.value:
                    continue
                if line_nr > last_line_number and \
                        line_nr < current_line_number:
                    skipped_notes.append((line_nr, note_type, note_text))
            last_line_number = current_line_number

        # Also collect the rest of the notes for this address.
        notes = []
        if note_level is not None:
            for note in memory_map.notes:
                note_address, line_nr, note_type, note_text = note
                if note_address != address:
                    continue
                if note_type.value > note_level.value:
                    continue
                # Skip notes that were already added above.
                if spread_notes and \
                        line_nr < tokens[0].line_nr:
                    continue
                notes.append((line_nr, note_type, note_text))

        # Add the notes from the tokens themselves.
        if add_token_notes:
            for token in tokens:
                if token.note:
                    notes.append((token.line_nr, NoteType.INFO, token.note))

        # Now we start building the output line with the compiled binary word.
        # We do this to indent notes and labels properly if needed.
        line = ""
        if add_address_numbers:
            line += f"{address:04}:  "
        if use_hashtags:
            word = word.replace('0', '-').replace('1', '#')
        line += word
        line_len = len(line)

        # Sort notes by note type severity
        skipped_notes.sort(key=lambda n: n[1].value)
        notes.sort(key=lambda n: n[1].value)

        # Format the text of the notes with their line numbers and types.
        skipped_notes_texts = [
            f"{note_type.name} line {line_nr}: {note_text}"
            for line_nr, note_type, note_text in skipped_notes]
        note_texts = [
            f"{note_type.name} line {line_nr}: {note_text}"
            for line_nr, note_type, note_text in notes]

        # If we are not spreading the notes and labels over multiple lines,
        # the process is simple: just append them to the line.
        if not spread_notes:
            if labels or show_token_src or note_texts:
                line += ' '
            if labels:
                line += f" {': '.join(labels)}:"
            if show_token_src:
                src_texts = [token.src_text for token in tokens]
                line += ' ' + ' '.join(src_texts)
            if note_texts:
                line += f" {' '.join([f"[{t}]" for t in note_texts])}"
            output.append(line)
            continue

        # Now that we know that we are spreading the notes and labels over
        # multiple lines, we can optionally put the token source texts on
        # the main line, as we don't have to put the label before it anymore.
        if show_token_src:
            src_texts = [token.src_text for token in tokens]
            line += '  ' + ' '.join(src_texts)

        # If word wrapping is enabled, wrap the notes accordingly.
        if word_wrap_limit is not None:
            wrapped_skipped_notes = []
            for note_text in skipped_notes_texts:
                wrapped = word_wrap(note_text,
                                    word_wrap_limit - line_len - 2,
                                    4)
                for wrapped_line in wrapped.splitlines():
                    wrapped_skipped_notes.append(wrapped_line)
            skipped_notes_texts = wrapped_skipped_notes
            wrapped_notes = []
            for note_text in note_texts:
                wrapped = word_wrap(note_text,
                                    word_wrap_limit - line_len - 2,
                                    4)
                for wrapped_line in wrapped.splitlines():
                    wrapped_notes.append(wrapped_line)
            note_texts = wrapped_notes

        # Now output the skipped notes, labels, and notes in order.
        for skipped_note_text in skipped_notes_texts:
            output.append(' ' * (line_len + 2) + skipped_note_text)
        for label in labels:
            if add_address_numbers:
                output.append(f"      {label}:")
            else:
                output.append(f"{label}:")
        if note_texts:
            if show_token_src:
                output.append(line)
            else:
                output.append(line + '  ' + note_texts[0])
                note_texts = note_texts[1:]
            for note_text in note_texts:
                output.append(' ' * (line_len + 2) + note_text)
        else:
            output.append(line)

    return '\n'.join(output)


def print_notes(memory_map: Memory_Map,
                note_level: NoteType | None = None,
                word_wrap_limit: int | None = None) -> None:
    errors = 0
    warnings = 0
    notes = sorted(memory_map.notes, key=lambda n: (n[2].value, n[0]))
    notes_printed = 0
    if not note_level:
        note_level = NoteType.WARNING
    last_note_level: NoteType | None = None
    for note in notes:
        address, line_nr, note_type, note_text = note
        if note_type == NoteType.ERROR:
            errors += 1
        elif note_type == NoteType.WARNING:
            warnings += 1
        if note_level is not None and note_type.value > note_level.value:
            continue
        notes_printed += 1
        if last_note_level is not None and note[2] != last_note_level:
            print()
        last_note_level = note[2]
        full_note = (f"Address {address:04}, Line {line_nr}, "
                     f"{note_type.name}: {note_text}")
        if word_wrap_limit is not None:
            wrapped_note = word_wrap(full_note, word_wrap_limit, 4)
            print(wrapped_note)
        else:
            print(full_note)
    if notes_printed > 0:
        print()
    print(f"Errors: {errors}, Warnings: {warnings}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description=("Compile 1bpc assembly source code into binary memory "
                     "map.\n"
                     "Examples:\n"
                     "  python main.py source.txt output.txt\n"
                     "  python main.py --show-labels --note-level info "
                     "--word-wrap-limit 80 --add-address-numbers"
                     "--add-token-notes source.txt "
                     "output.txt")
    )
    parser.add_argument("source_file", help="Path to the source code file.")
    parser.add_argument("output_file", nargs='?',
                        help="Path to the output file (optional).")
    parser.add_argument(
        "--show-labels",
        action="store_true",
        help="Show labels in the output."
    )
    parser.add_argument(
        "--note-level",
        choices=["error", "warning", "comment", "info"],
        help="Minimum note level to display."
    )
    parser.add_argument(
        "--spread-notes",
        action="store_true",
        help="Allow notes to be spread over multiple lines."
    )
    parser.add_argument(
        "--word-wrap-limit",
        type=int,
        help="Set word wrap limit for notes."
    )
    parser.add_argument(
        "--add-address-numbers",
        action="store_true",
        help="Add address numbers to the output."
    )
    parser.add_argument(
        "--show-token-src",
        action="store_true",
        help="Show the source text of each token in the output."
    )
    parser.add_argument(
        "--add-token-notes",
        action="store_true",
        help="Add token notes to the output."
    )
    parser.add_argument(
        "--use-hashtags",
        action="store_true",
        help="Use '#' for 1s and '-' for 0s in the binary output."
    )
    parser.add_argument(
        "--auto-recompile",
        action="store_true",
        help="Automatically recompile on source file changes."
    )
    parser.add_argument(
        "--export-mtech",
        action="store_true",
        help="Export the compiled memory map to the MTech workshop data.json "
        "file."
    )
    args = parser.parse_args()

    note_level: NoteType | None = None
    note_level_map = {
        "error": NoteType.ERROR,
        "warning": NoteType.WARNING,
        "comment": NoteType.COMMENT,
        "info": NoteType.INFO
    }
    if args.note_level:
        if args.note_level in note_level_map:
            note_level = note_level_map[args.note_level]
        else:
            print(f"Invalid note level: {args.note_level}")
            exit(1)

    if args.word_wrap_limit is not None and args.word_wrap_limit < 40:
        print("Word wrap limit must be at least 40.")
        exit(1)

    if args.word_wrap_limit is not None:
        args.spread_notes = True

    def compile_and_output():
        start_time = time.time()

        print(f"Reading {args.source_file}...")

        with open(args.source_file, 'r') as f:
            source_code = f.read()

        print("Compiling source code...")

        memory_map = compile_source(source_code)

        print("Generating output...")

        output = get_output(
            memory_map,
            show_labels=args.show_labels,
            note_level=note_level,
            spread_notes=args.spread_notes,
            word_wrap_limit=args.word_wrap_limit,
            add_address_numbers=args.add_address_numbers,
            show_token_src=args.show_token_src,
            add_token_notes=args.add_token_notes,
            use_hashtags=args.use_hashtags
        )

        if args.output_file:
            output_file = args.output_file
        else:
            output_file = "compiled.txt"

        print(f"Writing output to {output_file}...")

        with open(output_file, 'w') as f:
            f.write(output)

        if args.export_mtech:
            print("Exporting memory map to MTech data.json...")
            export_memory_map(memory_map)

        print("Done.")

        print("")

        print_notes(memory_map, note_level, args.word_wrap_limit)
        print(f"Finished in {time.time() - start_time:.4f} seconds.")

    compile_and_output()

    if not args.auto_recompile:
        exit(0)

    import os

    last_mtime = os.path.getmtime(args.source_file)
    print("Watching for changes...")
    try:
        while True:
            time.sleep(.1)
            current_mtime = os.path.getmtime(args.source_file)
            if current_mtime != last_mtime:
                print("\nSource file changed, recompiling...\n")
                compile_and_output()
                last_mtime = current_mtime
                print("Watching for changes...")
    except KeyboardInterrupt:
        print("\nExiting.")
