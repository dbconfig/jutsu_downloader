

def remove_all_non_ntfs_symbols(filename: str) -> str:
    if not filename:
        return filename

    forbidden = '\\/*:?|"<>'
    for symbol in forbidden:
        filename.replace(symbol, '')
    return filename
