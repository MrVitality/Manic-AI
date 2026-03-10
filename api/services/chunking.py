from typing import List, Dict


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[Dict]:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = " ".join(text.split())
    if len(text) <= chunk_size:
        return [{"content": text, "index": 0, "start": 0, "end": len(text)}]
    chunks = []
    start = 0
    index = 0
    while start < len(text):
        end = start + chunk_size
        if end < len(text):
            last_period = text.rfind(".", start, end)
            last_newline = text.rfind("\n", start, end)
            break_point = max(last_period, last_newline)
            if break_point > start + chunk_size * 0.5:
                end = break_point + 1
        chunk = text[start:end].strip()
        if chunk:
            chunks.append({"content": chunk, "index": index, "start": start, "end": end})
            index += 1
        start = end - overlap
        if start >= len(text) - overlap:
            break
    return chunks
