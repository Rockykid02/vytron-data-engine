import hashlib, re
from pathlib import Path
from bs4 import BeautifulSoup
from pypdf import PdfReader
from ebooklib import epub, ITEM_DOCUMENT

def clean_text(text):
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

def detect_language(text):
    # Lightweight flag only; native-speaker review is required.
    s = " " + text.lower() + " "
    markers = [" ndiri ", " wakadii", " makadii", " zvakanaka", " munhu ", " mwana ",
               " kuti ", " ndiye ", " henyu", " ndinoda", " chirevo", " zvangu "]
    hits = sum(s.count(x) for x in markers)
    return "sn" if hits >= 2 else ("sn-review" if hits == 1 else "unknown")

def extract_file(path: Path):
    ext = path.suffix.lower()
    if ext == ".txt":
        return path.read_text(encoding="utf-8", errors="replace")
    if ext == ".pdf":
        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    if ext == ".epub":
        book = epub.read_epub(str(path))
        out = []
        for item in book.get_items_of_type(ITEM_DOCUMENT):
            out.append(BeautifulSoup(item.get_content(), "html.parser").get_text(" ", strip=True))
        return "\n".join(out)
    raise ValueError("Supported formats: PDF, EPUB, TXT")

def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
