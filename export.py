from pathlib import Path
from memory_map import Memory_Map
import json

DEFAULT_FILE_PATH = ("C:/Program Files (x86)/Steam/steamapps/workshop/content/"
                     "387990/3100500975/memoryBlockData/data.json")


def export_memory_map(
    memory_map: Memory_Map,
    file_path: Path = Path(DEFAULT_FILE_PATH)
) -> None:
    """Export the given memory map to the specified file path in JSON format.

    Args:
        memory_map (MemoryMap): The memory map to export.
        file_path (Path, optional): The file path to export to. Defaults to
            the predefined path.
    """

    output = {"data": [f"0b{byte}" for byte in memory_map.binary]}

    with open(file_path, "w", encoding="utf-8") as file:
        json.dump(output, file, indent=4)
