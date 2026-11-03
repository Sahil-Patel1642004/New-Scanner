from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import asynccontextmanager
from datetime import datetime
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import Annotated, NamedTuple, Optional

import pymupdf
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# APP PATH
if getattr(sys, "frozen", False):
    # PyInstaller EXE
    APP_DIR = Path(sys._MEIPASS)
else:
    # Normal Python
    APP_DIR = Path(__file__).resolve().parent.parent

# SUPPORTED IMAGE EXTENSIONS
IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".bmp",
    ".gif",
    ".tif",
    ".tiff",
    ".webp",
}
SUPPORTED_EXTENSIONS = IMAGE_EXTENSIONS | {".pdf"}
OCR_MAX_DIMENSION = 2200
OCR_BATCH_SIZE = 50
OCR_WORKER_LIMIT = 6
OCR_PIPELINE_VERSION = 14


def _run_tesseract(executable: Path, arguments: list, env=None):
    return subprocess.run(
        [str(executable), *arguments],
        capture_output=True,
        env=env,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


# TKINTER - FOLDER PICKER
try:
    import tkinter as tk
    from tkinter import filedialog
except ImportError:
    tk = None
    filedialog = None

# OCR / TESSERACT
OCR_AVAILABLE = False
pytesseract = None
Image = None
OCR_ERROR = ""

try:
    import pytesseract
    from PIL import Image, ImageChops, ImageEnhance, ImageFilter, ImageOps
    def configure_tesseract():
        """
        Priority:
        1. PyInstaller bundled Tesseract
        2. Local project Tesseract
        3. TESSERACT_CMD environment variable
        4. Normal Windows Tesseract installation
        """
        candidates = []
        # PyInstaller EXE
        if getattr(sys, "frozen", False):
            base = Path(sys._MEIPASS)
            candidates.extend([
                base / "tesseract" / "tesseract.exe",
                base / "tesseract" / "bin" / "tesseract.exe",
            ])
        else:
            candidates.extend([
                APP_DIR / "tesseract" / "tesseract.exe",
                APP_DIR / "tesseract" / "bin" / "tesseract.exe",
            ])
        # Environment variable
        env_path = os.environ.get("TESSERACT_CMD")
        if env_path:
            candidates.insert(
                0,
                Path(env_path)
            )
        # Normal Windows installation
        candidates.extend([
            Path(
                r"C:\Program Files\Tesseract-OCR\tesseract.exe"
            ),
            Path(
                r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"
            ),
        ])
        # Find executable
        for exe in candidates:
            try:
                if exe.exists():
                    pytesseract.pytesseract.tesseract_cmd = str(exe)
                    # tessdata folder
                    tessdata = exe.parent / "tessdata"
                    if tessdata.exists():
                        os.environ["TESSDATA_PREFIX"] = str(
                            tessdata
                        )
                    return True
            except Exception:
                continue
        return False

    # Configure Tesseract
    if configure_tesseract():
        try:
            result = _run_tesseract(
                Path(pytesseract.pytesseract.tesseract_cmd),
                ["--version"],
            )
            if result.returncode == 0:
                OCR_AVAILABLE = True
            else:
                OCR_ERROR = "Tesseract was found but could not start."
        except Exception:
            OCR_AVAILABLE = False
            OCR_ERROR = "Tesseract was found but could not start."
    else:
        OCR_AVAILABLE = False
        OCR_ERROR = "Tesseract executable or English language data was not found."
except Exception:
    OCR_AVAILABLE = False
    pytesseract = None
    Image = None
    OCR_ERROR = "Python OCR packages are not available."

# FASTAPI
@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield


app = FastAPI(
    title="Prakshal-Scanora Search",
    lifespan=lifespan,
)
# In-memory working index backed by a local JSON cache.
index_lock = threading.Lock()
image_index = {}


def _index_cache_path() -> Path:
    cache_root = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".smart_image_search"))
    return cache_root / "SmartImageSearch" / "index.json"


def _settings_cache_path() -> Path:
    return _index_cache_path().with_name("settings.json")


def load_last_scan_folder() -> Optional[str]:
    try:
        with _settings_cache_path().open("r", encoding="utf-8") as settings_file:
            settings = json.load(settings_file)
        folder = settings.get("last_scan_folder")
        return folder if isinstance(folder, str) and folder else None
    except (OSError, ValueError, TypeError):
        return None


def save_last_scan(folder: Path) -> None:
    settings_path = _settings_cache_path()
    temporary_path = settings_path.with_suffix(".tmp")
    try:
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        with temporary_path.open("w", encoding="utf-8") as settings_file:
            json.dump(
                {
                    "last_scan_folder": str(folder),
                    "last_scan_time": datetime.now().isoformat(timespec="seconds"),
                },
                settings_file,
                ensure_ascii=True,
            )
        os.replace(temporary_path, settings_path)
    except OSError:
        try:
            temporary_path.unlink(missing_ok=True)
        except OSError:
            pass


def load_index() -> None:
    try:
        with _index_cache_path().open("r", encoding="utf-8") as cache_file:
            cached_index = json.load(cache_file)
        if isinstance(cached_index, dict):
            image_index.update(
                {
                    path: record
                    for path, record in cached_index.items()
                    if isinstance(path, str) and isinstance(record, dict)
                }
            )
    except (OSError, ValueError, TypeError):
        pass


def save_index() -> None:
    cache_path = _index_cache_path()
    temporary_path = cache_path.with_suffix(".tmp")
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with temporary_path.open("w", encoding="utf-8") as cache_file:
            json.dump(image_index, cache_file, ensure_ascii=True, separators=(",", ":"))
        os.replace(temporary_path, cache_path)
    except OSError:
        try:
            temporary_path.unlink(missing_ok=True)
        except OSError:
            pass


def clear_index() -> None:
    """Drop the cached index so the next launch starts from a clean database."""
    with index_lock:
        image_index.clear()
    _invalidate_search_cache()

    for cache_file in (_index_cache_path(), _index_cache_path().with_suffix(".tmp")):
        try:
            cache_file.unlink(missing_ok=True)
        except OSError:
            pass

    # Word boxes belong to the cleared index, so they go with it.
    try:
        boxes_dir = _word_box_cache_dir()
        if boxes_dir.is_dir():
            for box_file in boxes_dir.glob("*.json"):
                try:
                    box_file.unlink(missing_ok=True)
                except OSError:
                    pass
    except OSError:
        pass


# FAST SEARCH CACHE
# Searching rebuilds nothing per keystroke: lowercased fields and digit groups
# are prepared once per index change and rows are kept pre-sorted by filename.
_search_lock = threading.Lock()
_search_rows: list = []
_search_dirty = True


class SearchRow(NamedTuple):
    filename: str
    folder: str
    text: str
    compact_text: str
    compact_filename: str
    compact_folder: str
    text_padded: str
    filename_padded: str
    filename_tokens: tuple
    folder_tokens: tuple
    text_tokens: tuple
    number_tokens: tuple
    numbers: tuple
    date: str
    modified: float
    path: str
    record: dict


def _build_search_row(path: str, record: dict) -> SearchRow:
    filename = str(record.get("filename", "") or "")
    folder = str(record.get("folder", "") or "")
    text = str(record.get("text", "") or "")
    filename_key = filename.casefold()
    folder_key = folder.casefold()
    text_key = text.casefold()
    filename_tokens = tuple(dict.fromkeys(re.findall(r"[a-z0-9]+", filename_key)))
    folder_tokens = tuple(dict.fromkeys(re.findall(r"[a-z0-9]+", folder_key)))
    text_tokens = tuple(dict.fromkeys(re.findall(r"[a-z0-9]+", text_key)))
    try:
        modified = float(record.get("modified"))
    except (TypeError, ValueError):
        modified = 0.0
    try:
        date_key = datetime.fromtimestamp(modified).strftime("%Y-%m-%d")
    except (OSError, OverflowError, ValueError):
        date_key = ""
    return SearchRow(
        filename=filename_key,
        folder=folder_key,
        text=text_key,
        # Compact keys help match IDs even when OCR inserts spaces or punctuation:
        # "AB 123-45" can match a query for "AB12345".
        compact_text=re.sub(r"[^a-z0-9]+", "", text_key),
        compact_filename=re.sub(r"[^a-z0-9]+", "", filename_key),
        compact_folder=re.sub(r"[^a-z0-9]+", "", folder_key),
        # Padded copies make whole-word checks a plain substring test.
        text_padded=f" {text_key} ",
        filename_padded=f" {filename_key} ",
        filename_tokens=filename_tokens,
        folder_tokens=folder_tokens,
        text_tokens=text_tokens,
        number_tokens=tuple(dict.fromkeys(filename_tokens + text_tokens)),
        numbers=tuple(re.findall(r"\d+", filename + " " + text)),
        date=date_key,
        modified=modified,
        path=path,
        record=record,
    )


_OCR_NUMBER_TRANSLATION = str.maketrans({
    "o": "0",
    "q": "0",
    "i": "1",
    "l": "1",
    "z": "2",
    "s": "5",
    "g": "6",
    "b": "8",
})
_DECIMAL_NUMBER_PATTERN = re.compile(
    r"(?<![a-z0-9])[0-9oqilzsgb]+(?:[.,][0-9oqilzsgb]+)+(?![a-z0-9])",
    re.IGNORECASE,
)
_DECIMAL_QUERY_PATTERN = re.compile(r"^\d+[.,]\d+(?:[.,]\d+)*$")


def _query_terms(value: str) -> list:
    """Keep decimal numbers intact while splitting ordinary query words."""
    return re.findall(r"[a-z0-9]+(?:[.,][0-9]+)*", value.casefold())


def _decimal_number_matches(needle: str, haystacks) -> bool:
    normalized_needle = needle.casefold().translate(_OCR_NUMBER_TRANSLATION)
    return any(
        token.casefold().translate(_OCR_NUMBER_TRANSLATION) == normalized_needle
        for haystack in haystacks
        for token in _DECIMAL_NUMBER_PATTERN.findall(haystack)
    )


def _ocr_number_match(needle: str, tokens) -> bool:
    """Match common OCR letter/number substitutions in numeric identifiers."""
    if not any(character.isdigit() for character in needle):
        return False
    normalized_needle = needle.translate(_OCR_NUMBER_TRANSLATION)
    return any(
        any(character.isdigit() for character in token)
        and normalized_needle in token.translate(_OCR_NUMBER_TRANSLATION)
        for token in tokens
    )


def _numbers_match(row: SearchRow, needle: str, fuzzy: bool = False) -> bool:
    """Match a numeric query against each digit group, not the joined string."""
    if not needle:
        return True
    if _DECIMAL_QUERY_PATTERN.fullmatch(needle):
        return _decimal_number_matches(
            needle,
            (row.filename, row.text),
        )
    exact_match = (
        any(needle in group for group in row.numbers)
        or _ocr_number_match(needle, row.number_tokens)
    )
    return exact_match or (
        fuzzy and _fuzzy_numeric_match(needle, row.number_tokens)
    )


def _edit_distance_at_most(first: str, second: str, limit: int):
    """Return a small Damerau-Levenshtein distance, or None beyond the limit."""
    if abs(len(first) - len(second)) > limit:
        return None
    previous_previous = None
    previous = list(range(len(second) + 1))
    for first_index, first_character in enumerate(first, start=1):
        current = [first_index]
        for second_index, second_character in enumerate(second, start=1):
            distance = min(
                previous[second_index] + 1,
                current[second_index - 1] + 1,
                previous[second_index - 1] + int(first_character != second_character),
            )
            if (
                previous_previous is not None
                and first_index > 1
                and second_index > 1
                and first_character == second[second_index - 2]
                and first[first_index - 2] == second_character
            ):
                distance = min(distance, previous_previous[second_index - 2] + 1)
            current.append(distance)
        previous_previous, previous = previous, current
    distance = previous[-1]
    return distance if distance <= limit else None


def _fuzzy_term_distance(term: str, tokens):
    if term.isdigit() or len(term) < 4:
        return None
    limit = 1 if len(term) < 7 else 2
    distances = (
        _edit_distance_at_most(term, candidate, limit)
        for candidate in tokens
    )
    return min((distance for distance in distances if distance is not None), default=None)


def _fuzzy_numeric_match(needle: str, tokens) -> bool:
    if not needle.isdigit() or len(needle) < 6:
        return False
    for token in tokens:
        candidate = token.translate(_OCR_NUMBER_TRANSLATION)
        if candidate.isdigit() and len(candidate) == len(needle):
            if sum(first != second for first, second in zip(needle, candidate)) == 1:
                return True
    return False


def _parse_search_query(query: str):
    """Parse implicit/explicit AND, OR alternatives, and quoted phrases."""
    if query.count('"') % 2:
        raise ValueError("Search query has an unmatched quotation mark.")

    tokens = []
    pattern = re.compile(r'"([^"]*)"|\b(AND|OR)\b|([^\s"]+)', re.IGNORECASE)
    for match in pattern.finditer(query):
        if match.group(1) is not None:
            phrase = match.group(1).strip()
            if not phrase:
                raise ValueError("Quoted search phrases cannot be empty.")
            tokens.append(("phrase", phrase.casefold()))
        elif match.group(2) is not None:
            tokens.append(("operator", match.group(2).upper()))
        else:
            tokens.append(("term", match.group(3).casefold()))

    clauses = []
    current_clause = []
    expecting_operand = False
    for kind, value in tokens:
        if kind != "operator":
            current_clause.append((value, kind == "phrase"))
            expecting_operand = False
            continue
        if expecting_operand or not current_clause:
            raise ValueError(f"Unexpected {value} operator in search query.")
        if value == "OR":
            clauses.append(current_clause)
            current_clause = []
        expecting_operand = True

    if expecting_operand:
        raise ValueError("Search query cannot end with AND or OR.")
    if current_clause:
        clauses.append(current_clause)
    return clauses


def search_highlight_terms(query: str) -> list:
    """Return positive query words for result and image-match highlighting."""
    clauses = _parse_search_query(query)
    return [
        word
        for clause in clauses
        for value, _ in clause
        for word in _query_terms(value)
    ]


def search_term_matches(
    term: str,
    text: str,
    *,
    allow_fuzzy_numeric: bool = True,
) -> bool:
    """Check one query term against a displayable filename or OCR word."""
    term = term.casefold()
    candidate = text.casefold()
    if _DECIMAL_QUERY_PATTERN.fullmatch(term):
        return _decimal_number_matches(term, (candidate,))
    if term in candidate:
        return True
    tokens = re.findall(r"[a-z0-9]+", candidate)
    if _ocr_number_match(term, tokens):
        return True
    if (
        allow_fuzzy_numeric
        and term.isdigit()
        and _fuzzy_numeric_match(term, tokens)
    ):
        return True
    return _fuzzy_term_distance(term, tokens) is not None


def _score_query_clause(row: SearchRow, clause: list, field: str, fuzzy: bool = False):
    """Return a relevance score for one AND clause, or None if it does not match."""
    if field == "name":
        haystacks = (row.filename,)
        tokens = row.filename_tokens
    elif field == "year":
        haystacks = (row.filename, row.text)
        tokens = row.filename_tokens + row.text_tokens
    elif field == "number":
        haystacks = (row.filename, row.text)
        tokens = row.filename_tokens + row.text_tokens
    else:
        haystacks = (row.filename, row.folder, row.text)
        tokens = row.filename_tokens + row.folder_tokens + row.text_tokens

    score = 0
    for term, is_phrase in clause:
        if field == "number" and not is_phrase:
            has_letters_and_digits = (
                any(character.isalpha() for character in term)
                and any(character.isdigit() for character in term)
            )
            compact_term = re.sub(r"[^a-z0-9]+", "", term.casefold())
            compact_match = has_letters_and_digits and bool(compact_term) and any(
                compact_term in compact_haystack
                for compact_haystack in (
                    row.compact_filename,
                    row.compact_text,
                )
            )
            if not _numbers_match(row, term, fuzzy=fuzzy) and not compact_match:
                return None
            score += 20 if compact_match else 15
            continue
        if field == "date":
            if term not in row.date:
                return None
            score += 10
            continue

        if _DECIMAL_QUERY_PATTERN.fullmatch(term):
            exact_match = _decimal_number_matches(term, haystacks)
        else:
            exact_match = any(term in haystack for haystack in haystacks)
            # OCR commonly splits serial numbers across spaces, hyphens, or
            # punctuation. Use compact matching only for mixed letter/number IDs
            # to avoid broadening ordinary word searches unnecessarily.
            has_letters_and_digits = (
                any(character.isalpha() for character in term)
                and any(character.isdigit() for character in term)
            )
            if not exact_match and has_letters_and_digits and not is_phrase:
                compact_term = re.sub(r"[^a-z0-9]+", "", term.casefold())
                compact_haystacks = (
                    row.compact_filename,
                    row.compact_folder,
                    row.compact_text,
                )
                exact_match = bool(compact_term) and any(
                    compact_term in value for value in compact_haystacks
                )
        if is_phrase:
            if not exact_match:
                return None
            score += 50
            continue

        if _DECIMAL_QUERY_PATTERN.fullmatch(term) and not exact_match:
            return None
        if not exact_match and not _ocr_number_match(term, tokens):
            if not fuzzy:
                return None
            if term.isdigit():
                if not _fuzzy_numeric_match(term, tokens):
                    return None
                distance = 1
            else:
                distance = _fuzzy_term_distance(term, tokens)
                if distance is None:
                    return None
            term_score = max(1, 10 - distance)
        else:
            term_score = 20
            if term in row.filename:
                if row.filename.startswith(term):
                    term_score += 60
                if f" {term} " in row.filename_padded:
                    term_score += 40
            if term in row.text:
                if f" {term} " in row.text_padded:
                    term_score += 15
        score += term_score

    if field not in {"number", "date"} and not any(is_phrase for _, is_phrase in clause):
        phrase = " ".join(term for term, _ in clause)
        if row.filename == phrase:
            score += 200
        elif row.filename.startswith(phrase):
            score += 120
        elif phrase in row.filename:
            score += 80
        if field in {"all", "year"} and phrase in row.text:
            score += 40
        if field == "all" and phrase in row.folder:
            score += 10
    return score


def _snippet(row: SearchRow, terms: list, phrase: str, width: int = 160) -> str:
    """Return the OCR text window around the first match, for the result list."""
    haystack = row.text
    if not haystack:
        return ""
    position = -1
    for needle in [phrase, *terms]:
        if not needle:
            continue
        position = haystack.find(needle)
        if position != -1:
            break
    if position == -1:
        for match in re.finditer(r"[a-z0-9]+", haystack):
            if any(
                _ocr_number_match(term, (match.group(),))
                or _fuzzy_term_distance(term, (match.group(),)) is not None
                for term in terms
            ):
                position = match.start()
                break
    if position == -1:
        return haystack[:width].strip()
    start = max(0, position - width // 3)
    end = min(len(haystack), start + width)
    start = max(0, end - width)
    snippet = haystack[start:end].strip()
    if start > 0:
        snippet = f"...{snippet}"
    if end < len(haystack):
        snippet = f"{snippet}..."
    return snippet


def _invalidate_search_cache() -> None:
    global _search_dirty
    with _search_lock:
        _search_dirty = True


def _searchable_rows() -> list:
    global _search_rows, _search_dirty
    with _search_lock:
        if not _search_dirty:
            return _search_rows
    with index_lock:
        rows = [
            _build_search_row(path, record)
            for path, record in image_index.items()
        ]
    rows.sort(key=lambda row: row.filename)
    with _search_lock:
        _search_rows = rows
        _search_dirty = False
    return rows


load_index()

# IMAGE CHECK
def is_image(path: Path) -> bool:
    return (
        path.is_file()
        and path.suffix.lower() in IMAGE_EXTENSIONS
    )


def find_supported_files(base: Path):
    """Yield supported paths with modification times and sizes from scandir."""
    found, _ = _discover_supported_files(base)
    yield from found


def _discover_supported_files(base: Path, progress_callback=None) -> tuple:
    """Find supported files and count folders in one non-following traversal."""
    directories = [base]
    found = []
    folder_count = 1
    entries_seen = 0

    while directories:
        directory = directories.pop()
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    entries_seen += 1
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            folder_count += 1
                            directories.append(Path(entry.path))
                        elif (
                            entry.is_file(follow_symlinks=False)
                            and Path(entry.name).suffix.lower() in SUPPORTED_EXTENSIONS
                        ):
                            stat = entry.stat(follow_symlinks=False)
                            found.append((Path(entry.path), stat.st_mtime, stat.st_size))
                    except (OSError, PermissionError):
                        continue
                    if progress_callback and entries_seen % 256 == 0:
                        progress_callback({
                            "phase": "discovering",
                            "folder": str(base),
                            "folders": folder_count,
                            "total_files": len(found),
                            "scanned": 0,
                            "remaining": 0,
                        })
        except (OSError, PermissionError):
            continue
    return found, folder_count


# OCR IMAGE
def _flatten_transparency(image):
    if image.mode not in {"RGBA", "LA"} and "transparency" not in image.info:
        return image.copy()
    rgba = image.convert("RGBA")
    background = Image.new("RGBA", rgba.size, "white")
    try:
        return Image.alpha_composite(background, rgba).convert("RGB")
    finally:
        background.close()
        rgba.close()


def _clean_ocr_text(text: str) -> str:
    """Normalize whitespace without deleting valid single-letter OCR tokens.

    The previous implementation removed isolated letters, which can destroy
    initials, labels, table columns, and identifiers such as ``A 12345``.
    """
    cleaned = " ".join(
        " ".join(line.split())
        for line in text.splitlines()
        if line.strip()
    )
    return re.sub(r"\s{2,}", " ", cleaned).strip()


def extract_pdf_text(path: Path) -> str:
    """Extract PDF text, using OCR for scanned or suspiciously sparse image pages."""
    page_texts = []
    with pymupdf.open(path) as document:
        if document.needs_pass:
            raise ValueError(f"PDF is password-protected: {path.name}")
        for page in document:
            text = page.get_text("text").strip()

            # Some PDFs have a partial/incomplete text layer alongside a scanned
            # page image. OCR only when the embedded text is absent or unusually
            # sparse on a page that also contains images.
            has_page_images = bool(page.get_images())
            should_ocr = OCR_AVAILABLE and (
                not text or (has_page_images and len(text) < 80)
            )
            if should_ocr:
                try:
                    pixmap = page.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)
                    ocr_text = _ocr_image_bytes(pixmap.tobytes("png")).strip()
                    # Prefer the fuller result rather than concatenating both
                    # complete-page readings, which often duplicates every word.
                    if len(ocr_text) > len(text):
                        text = ocr_text
                except Exception:
                    # Keep any embedded text if rendering/OCR fails.
                    pass
            if text:
                page_texts.append(text)
    return _clean_ocr_text("\n".join(page_texts))


def _ocr_image_bytes(image_data: bytes) -> str:
    global OCR_ERROR
    executable = _tesseract_executable()
    if executable is None:
        return ""
    with tempfile.TemporaryDirectory(prefix="smart_ocr_") as workdir:
        best_result, best_confidence = _run_ocr_pass(
            executable, image_data, Path(workdir), "standard", psm=6
        )
        best_result = best_result or ("", [])
        if best_confidence < 80 or len(best_result[0].split()) < 6:
            for preprocessing in ("local_contrast", "adaptive_threshold"):
                try:
                    candidate, candidate_confidence = _run_ocr_pass(
                        executable,
                        image_data,
                        Path(workdir),
                        preprocessing,
                        psm=6,
                    )
                except (OSError, RuntimeError, ValueError) as error:
                    OCR_ERROR = f"PDF page OCR retry failed: {error}"
                    continue
                if candidate and _ocr_result_score(
                    candidate, candidate_confidence
                ) > _ocr_result_score(best_result, best_confidence):
                    best_result, best_confidence = candidate, candidate_confidence
        return _clean_ocr_text(best_result[0])


def ocr_image(path: Path) -> str:
    return ocr_image_with_words(path)[0]


def ocr_image_with_words(path: Path):
    """Return (text, words) where each word carries a normalized box.

    Boxes use 0..1 ratios of the OCR'd image, so they can be mapped onto any
    rendered size without depending on the OCR downscale factor.
    """
    global OCR_ERROR

    if not OCR_AVAILABLE:
        return "", []

    try:
        global OCR_ERROR

        executable = _tesseract_executable()
        if executable is None:
            raise OSError("Tesseract executable is unavailable.")
        with tempfile.TemporaryDirectory(prefix="smart_ocr_") as workdir:
            best_result, best_confidence = _run_ocr_pass(
                executable, path, Path(workdir), "standard"
            )
            best_result = best_result or ("", [])
            # Automatic page segmentation can miss table rows while reporting
            # high confidence for the page header. Try a block-oriented layout
            # when the first pass yields relatively few recognized words.
            has_lot_heading = (
                "lot" in best_result[0].casefold()
                and "number" in best_result[0].casefold()
            )
            has_six_digit_id = bool(
                re.search(r"(?<!\d)\d{6}(?!\d)", best_result[0])
            )
            missing_lot_row_id = any(
                not re.search(
                    r"(?<!\d)\d{5,7}(?!\d)",
                    best_result[0][max(0, size_match.start() - 36) : size_match.start()],
                )
                for size_match in re.finditer(
                    r"\b\d{2,3}\s*[xX×]\s*\d{2,3}\b",
                    best_result[0],
                )
            )
            needs_table_retry = has_lot_heading and (
                missing_lot_row_id or not has_six_digit_id
            )
            if len(best_result[1]) < 140 or needs_table_retry:
                try:
                    candidate, candidate_confidence = _run_ocr_pass(
                        executable,
                        path,
                        Path(workdir),
                        "standard",
                        psm=6,
                    )
                except (OSError, RuntimeError, ValueError):
                    candidate = None
                    candidate_confidence = 0.0
                if candidate and _ocr_result_score(
                    candidate, candidate_confidence
                ) > _ocr_result_score(best_result, best_confidence):
                    best_result, best_confidence = candidate, candidate_confidence
                if candidate and needs_table_retry:
                    best_result = _merge_numeric_ocr_ids(best_result, candidate)

            # Contrast passes are expensive. Use them only when both layouts
            # still leave most of the page unread, rather than for low average
            # confidence alone on otherwise text-rich pages.
            if len(best_result[1]) < 80:
                for preprocessing in ("local_contrast", "adaptive_threshold"):
                    try:
                        candidate, candidate_confidence = _run_ocr_pass(
                            executable, path, Path(workdir), preprocessing
                        )
                    except (OSError, RuntimeError, ValueError) as error:
                        OCR_ERROR = (
                            f"OCR {preprocessing.replace('_', ' ')} retry failed "
                            f"for {path.name}: {error}. Kept available OCR results."
                        )
                        continue
                    if candidate and _ocr_result_score(
                        candidate, candidate_confidence
                    ) > _ocr_result_score(best_result, best_confidence):
                        best_result, best_confidence = candidate, candidate_confidence

            # Try alternate orientations only when the best current result looks weak.
            if len(best_result[1]) < 80:
                for rotation in (90, 270, 180):
                    try:
                        candidate, candidate_confidence = _run_ocr_pass(
                            executable,
                            path,
                            Path(workdir),
                            "standard",
                            rotation=rotation,
                        )
                    except (OSError, RuntimeError, ValueError):
                        continue
                    if candidate and _ocr_result_score(
                        candidate, candidate_confidence
                    ) > _ocr_result_score(best_result, best_confidence):
                        best_result, best_confidence = candidate, candidate_confidence
            text, words = best_result
            return _clean_ocr_text(text), words
    except Exception:
        OCR_ERROR = f"OCR failed for {path.name}."
        return "", []


def _run_ocr_pass(
    executable: Path,
    source: Path | bytes,
    workdir: Path,
    preprocessing: str,
    psm: int = 3,
    rotation: int = 0,
) -> tuple[Optional[tuple], float]:
    input_path = workdir / f"image_{preprocessing}.png"
    if not _write_ocr_input(
        source, input_path, preprocessing=preprocessing, rotation=rotation
    ):
        raise OSError(f"Could not prepare the {preprocessing.replace('_', ' ')} image.")
    output_base = workdir / f"ocr_{preprocessing}"
    result = _run_tesseract_tsv(
        executable, input_path, output_base, psm=psm
    )
    try:
        confidence = _average_tesseract_confidence(output_base.with_suffix(".tsv"))
    except OSError:
        confidence = 0.0
    if result and rotation:
        result = _rotate_word_boxes_back(result, rotation)
    return result, confidence


def _ocr_result_score(result: Optional[tuple], confidence: float) -> float:
    if not result:
        return 0.0
    text, words = result
    # Prefer passes that recover substantially more of the page, while still
    # giving OCR confidence some weight. Dense tables often contain many useful
    # low-confidence tokens that page-level segmentation misses.
    return (
        confidence * 0.25
        + min(len(words), 400)
        + min(len(text.split()), 400) * 0.25
    )


def _merge_numeric_ocr_ids(primary: tuple, alternate: tuple) -> tuple:
    """Keep extra six-digit IDs and their boxes from an alternate table pass."""
    primary_text, primary_words = primary
    _, alternate_words = alternate
    known_ids = set(re.findall(r"(?<!\d)\d{6}(?!\d)", primary_text))
    words = list(primary_words)
    additions = []

    for word in alternate_words:
        text = str(word.get("text", ""))
        digits = re.sub(r"\D", "", text)
        if (
            len(digits) != 6
            or digits in known_ids
            or float(word.get("x", 1)) > 0.22
            or not 0.35 <= float(word.get("y", 0)) <= 0.75
        ):
            continue
        known_ids.add(digits)
        additions.append(digits)
        words.append({**word, "text": digits})

    if additions:
        primary_text = _clean_ocr_text(
            f"{primary_text} {' '.join(additions)}"
        )
    return primary_text, words


def _rotate_word_boxes_back(result: Optional[tuple], rotation: int) -> Optional[tuple]:
    if not result or not rotation:
        return result
    text, words = result
    mapped = []
    for word in words:
        x, y, w, h = word["x"], word["y"], word["w"], word["h"]
        # PIL's positive rotation is counter-clockwise. Map all four corners
        # from the rotated image into normalized coordinates of the source.
        corners = [(x, y), (x + w, y), (x, y + h), (x + w, y + h)]
        if rotation == 90:
            points = [(1 - v, u) for u, v in corners]
        elif rotation == 270:
            points = [(v, 1 - u) for u, v in corners]
        else:
            points = [(1 - u, 1 - v) for u, v in corners]
        xs, ys = [p[0] for p in points], [p[1] for p in points]
        mapped.append({**word, "x": round(min(xs), 6), "y": round(min(ys), 6),
                       "w": round(max(xs) - min(xs), 6), "h": round(max(ys) - min(ys), 6)})
    return text, mapped


def _run_tesseract_tsv(
    executable: Path,
    input_path: Path,
    output_base: Path,
    psm: int = 3,
) -> Optional[tuple]:
    process = _run_tesseract(
        executable,
        [
            str(input_path),
            str(output_base),
            "--oem", "3",
            "--psm", str(psm),
            "-l", "eng",
            "--dpi", "300",
            "-c", "preserve_interword_spaces=1",
            "tsv",
        ],
        env={**os.environ, "OMP_THREAD_LIMIT": "1"},
    )
    if process.returncode != 0:
        raise RuntimeError("Tesseract OCR failed.")
    pages = _parse_tsv_pages(output_base.with_suffix(".tsv"))
    return pages[0] if pages else None


def _average_tesseract_confidence(tsv_path: Path) -> float:
    with tsv_path.open("r", encoding="utf-8", errors="replace") as handle:
        header = handle.readline().rstrip("\r\n").split("\t")
        try:
            level_column = header.index("level")
            confidence_column = header.index("conf")
            text_column = header.index("text")
        except ValueError:
            return 0.0

        confidences = []
        for line in handle:
            parts = line.rstrip("\r\n").split("\t")
            if (
                len(parts) <= max(level_column, confidence_column, text_column)
                or parts[level_column] != "5"
                or not parts[text_column].strip()
            ):
                continue
            try:
                confidence = float(parts[confidence_column])
            except ValueError:
                continue
            if confidence >= 0:
                confidences.append(confidence)
    return sum(confidences) / len(confidences) if confidences else 0.0


def _merge_ocr_results(primary: tuple, enhanced: Optional[tuple]) -> tuple:
    """Choose the more complete pass instead of concatenating conflicting OCR.

    The old implementation appended unrelated alternate-pass text to the
    primary result. That could create duplicate words and false search matches.
    Confidence-aware selection happens at the call sites; this helper is a
    conservative fallback for any remaining callers.
    """
    if not enhanced:
        return primary
    primary_text = _clean_ocr_text(primary[0] if primary else "")
    enhanced_text = _clean_ocr_text(enhanced[0] if enhanced else "")
    if not primary_text:
        return (enhanced_text, list(enhanced[1] or []))
    if not enhanced_text:
        return (primary_text, list(primary[1] or []))
    if primary_text.casefold() in enhanced_text.casefold():
        return (enhanced_text, list(enhanced[1] or []))
    if enhanced_text.casefold() in primary_text.casefold():
        return (primary_text, list(primary[1] or []))

    def quality(result, text):
        words = result[1] or []
        tokens = re.findall(r"[^\W_]+", text.casefold(), flags=re.UNICODE)
        unique_ratio = len(set(tokens)) / max(1, len(tokens))
        return (
            len(re.sub(r"\s+", "", text)),
            len(words),
            unique_ratio,
        )

    return (
        (enhanced_text, list(enhanced[1] or []))
        if quality(enhanced, enhanced_text) > quality(primary, primary_text)
        else (primary_text, list(primary[1] or []))
    )


def _word_box_cache_dir() -> Path:
    cache_root = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".smart_image_search"))
    return cache_root / "SmartImageSearch" / "word_boxes"


def _tesseract_executable() -> Optional[Path]:
    """Return the resolved tesseract binary, if one is configured."""
    if pytesseract is None:
        return None
    command = getattr(pytesseract.pytesseract, "tesseract_cmd", None)
    if not command:
        return None
    executable = Path(command)
    return executable if executable.exists() else None


def _write_ocr_input(
    source: Path | bytes,
    target: Path,
    preprocessing: str = "standard",
    rotation: int = 0,
) -> bool:
    """Prepare a standard, local-contrast, or thresholded OCR image."""
    try:
        image_source = io.BytesIO(source) if isinstance(source, bytes) else source
        with Image.open(image_source) as opened:
            image = ImageOps.exif_transpose(opened)
            image = _flatten_transparency(image)
            if rotation:
                image = image.rotate(rotation, expand=True)
            image = image.convert("L")
            if max(image.size) > OCR_MAX_DIMENSION:
                image.thumbnail(
                    (OCR_MAX_DIMENSION, OCR_MAX_DIMENSION),
                    Image.Resampling.LANCZOS,
                )
            if preprocessing in {"local_contrast", "adaptive_threshold"}:
                background = image.filter(
                    ImageFilter.GaussianBlur(
                        radius=max(8, min(image.size) / 60)
                    )
                )
                image = ImageOps.autocontrast(
                    ImageChops.subtract(image, background, offset=128)
                )
                image = image.filter(
                    ImageFilter.UnsharpMask(radius=2, percent=180, threshold=3)
                )
                if preprocessing == "adaptive_threshold":
                    threshold = _otsu_threshold(image)
                    image = image.point(
                        lambda value: 255 if value > threshold else 0
                    )
            else:
                image = ImageOps.autocontrast(image)
                image = ImageEnhance.Contrast(image).enhance(1.7)
                image = image.filter(ImageFilter.SHARPEN)
            if max(image.size) < 2000:
                image = image.resize(
                    (image.width * 2, image.height * 2),
                    Image.Resampling.LANCZOS,
                )
            image.thumbnail(
                (OCR_MAX_DIMENSION, OCR_MAX_DIMENSION),
                Image.Resampling.LANCZOS,
            )
            image.save(target, format="PNG", compress_level=1)
        return True
    except Exception:
        return False


def _otsu_threshold(image) -> int:
    histogram = image.histogram()
    total = sum(histogram)
    weighted_total = sum(value * count for value, count in enumerate(histogram))
    background_weight = 0
    background_total = 0
    maximum_variance = -1.0
    threshold = 127
    for value, count in enumerate(histogram):
        background_weight += count
        if not background_weight:
            continue
        foreground_weight = total - background_weight
        if not foreground_weight:
            break
        background_total += value * count
        background_mean = background_total / background_weight
        foreground_mean = (weighted_total - background_total) / foreground_weight
        variance = (
            background_weight
            * foreground_weight
            * (background_mean - foreground_mean) ** 2
        )
        if variance > maximum_variance:
            maximum_variance = variance
            threshold = value
    return threshold


def _parse_tsv_pages(tsv_path: Path) -> list:
    """Parse a tesseract TSV file into per-page (text, words) results."""
    pages: dict = {}
    sizes: dict = {}
    try:
        with tsv_path.open("r", encoding="utf-8", errors="replace") as handle:
            header = handle.readline().rstrip("\n").split("\t")
            column = {name: position for position, name in enumerate(header)}
            required = ("level", "page_num", "left", "top", "width", "height", "text")
            if any(name not in column for name in required):
                return []
            for line in handle:
                parts = line.rstrip("\n").split("\t")
                if len(parts) < len(header):
                    continue
                try:
                    level = parts[column["level"]]
                    page = int(parts[column["page_num"]])
                    left = int(parts[column["left"]])
                    top = int(parts[column["top"]])
                    box_width = int(parts[column["width"]])
                    box_height = int(parts[column["height"]])
                except (TypeError, ValueError):
                    continue

                if level == "1":
                    # Page level row carries the rendered page size.
                    if box_width > 0 and box_height > 0:
                        sizes[page] = (box_width, box_height)
                    continue
                if level != "5":
                    continue

                word = parts[column["text"]].strip()
                if not word or box_width <= 0 or box_height <= 0:
                    continue
                try:
                    confidence_column = column["conf"]
                    block = parts[column["block_num"]]
                    paragraph = parts[column["par_num"]]
                    line = parts[column["line_num"]]
                    confidence = float(parts[confidence_column])
                except (KeyError, IndexError, TypeError, ValueError):
                    block = paragraph = line = "0"
                    confidence = -1.0
                if confidence < 0:
                    continue
                pages.setdefault(page, []).append(
                    (block, paragraph, line, word, left, top, box_width, box_height)
                )
    except OSError:
        return []

    results = []
    for page in sorted(pages):
        width, height = sizes.get(page, (0, 0))
        if not width or not height:
            continue
        words = []
        lines: dict = {}
        for block, paragraph, line, word, left, top, box_width, box_height in pages[page]:
            words.append({
                "text": word,
                "x": round(left / width, 6),
                "y": round(top / height, 6),
                "w": round(box_width / width, 6),
                "h": round(box_height / height, 6),
            })
            lines.setdefault((block, paragraph, line), []).append(word)
        text = " ".join(
            " ".join(parts)
            for _, parts in sorted(lines.items())
        )
        results.append((text, words))
    return results


def ocr_batch(
    paths: list,
    progress_callback=None,
    result_callback=None,
    retain_results: bool = True,
) -> dict:
    """OCR images in parallel, bounding Tesseract processes to available CPUs."""
    results: dict = {}
    if not OCR_AVAILABLE or not paths:
        return results

    completed = 0
    worker_count = max(1, min(OCR_WORKER_LIMIT, os.cpu_count() or 4, len(paths)))
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        for batch in _chunked(paths, OCR_BATCH_SIZE):
            futures = {
                executor.submit(ocr_image_with_words, entry[0]): entry
                for entry in batch
            }
            for future in as_completed(futures):
                entry = futures[future]
                try:
                    result = future.result()
                except Exception as error:
                    # A single corrupt image must not cancel the folder scan.
                    global OCR_ERROR
                    OCR_ERROR = f"OCR failed for {entry[0].name}: {error}"
                    result = ("", [])
                completed += 1
                if retain_results:
                    results[entry[1]] = result
                if result_callback:
                    result_callback(entry, result)
                if progress_callback:
                    progress_callback(completed)

    return results


def _chunked(items: list, size: int):
    for start in range(0, len(items), size):
        yield items[start:start + size]


def _word_box_cache_file(path: Path) -> Path:
    key = hashlib.sha1(str(path).casefold().encode("utf-8")).hexdigest()
    return _word_box_cache_dir() / f"{key}.json"



def load_word_boxes(path: str) -> list:
    """Load cached OCR boxes or generate them when possible."""
    source = Path(path)

    if not source.is_file() or source.suffix.casefold() == ".pdf":
        return []

    try:
        source_stat = source.stat()
        modified = source_stat.st_mtime
        size_bytes = source_stat.st_size
    except OSError:
        return []

    cache_file = _word_box_cache_file(source)

    # Check the cache BEFORE requiring Tesseract.
    try:
        with cache_file.open("r", encoding="utf-8") as handle:
            cached = json.load(handle)

        if (
            isinstance(cached, dict)
            and cached.get("modified") == modified
            and cached.get("size_bytes") == size_bytes
            and cached.get("ocr_pipeline_version") == OCR_PIPELINE_VERSION
            and isinstance(cached.get("words"), list)
        ):
            return cached["words"]

    except (OSError, ValueError, TypeError):
        pass

    # If no valid cache exists, OCR must be available.
    if not OCR_AVAILABLE:
        return []

    try:
        _, words = ocr_image_with_words(source)
    except Exception:
        return []

    try:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        temporary_file = cache_file.with_suffix(".tmp")

        with temporary_file.open("w", encoding="utf-8") as handle:
            json.dump(
                {
                    "modified": modified,
                    "size_bytes": size_bytes,
                    "ocr_pipeline_version": OCR_PIPELINE_VERSION,
                    "words": words,
                },
                handle,
                ensure_ascii=True,
                separators=(",", ":"),
            )

        temporary_file.replace(cache_file)

    except (OSError, TypeError, ValueError):
        pass
    print("VIEWER OCR BOXES:", words)
    return words
def scan_folder(folder: str, force_ocr: bool = False, progress_callback=None):
    base = Path(folder).expanduser().resolve()

    if not base.exists():
        raise ValueError("Folder does not exist.")
    if not base.is_dir():
        raise ValueError("Selected path is not a folder.")

    found, folder_count = _discover_supported_files(base, progress_callback)
    if progress_callback:
        progress_callback({
            "phase": "discovered",
            "folder": str(base),
            "folders": folder_count,
            "total_files": len(found),
            "scanned": 0,
            "remaining": len(found),
        })

    base_prefix = str(base) + os.sep
    with index_lock:
        old_by_path = {
            path: record.copy()
            for path, record in image_index.items()
            if path == str(base) or path.startswith(base_prefix)
        }

    pending = []
    pending_paths = set()
    for path, modified, size_bytes in found:
        try:
            path_string = str(path)
            previous = old_by_path.get(path_string)
            if previous and not force_ocr:
                try:
                    if (
                        float(previous.get("modified")) == modified
                        and int(previous.get("size_bytes", -1)) == size_bytes
                    ):
                        # Reprocess every supported file when the OCR pipeline
                        # changes, including PDFs. Previously PDFs bypassed this
                        # version check and could keep stale extracted text.
                        if (
                            previous.get("ocr_pipeline_version")
                            == OCR_PIPELINE_VERSION
                            and not previous.get("ocr_pending", False)
                        ):
                            continue
                except (TypeError, ValueError):
                    pass
            pending.append((path, path_string, modified, size_bytes))
            pending_paths.add(path_string)
        except (OSError, PermissionError):
            continue

    total_pending = len(pending)
    indexed_at = datetime.now().isoformat(timespec="seconds")
    existing_paths = {str(path) for path, _, _ in found}
    with index_lock:
        for path, modified, size_bytes in found:
            path_string = str(path)
            previous = old_by_path.get(path_string, {})
            try:
                same_source = (
                    float(previous.get("modified")) == modified
                    and int(previous.get("size_bytes", -1)) == size_bytes
                )
            except (TypeError, ValueError):
                same_source = False

            record = previous.copy() if same_source else {}
            record.update({
                "path": path_string,
                "filename": path.name,
                "folder": str(path.parent),
                "text": record.get("text", ""),
                "modified": modified,
                "size_bytes": size_bytes,
                "indexed_at": record.get("indexed_at", indexed_at),
                "ocr_pipeline_version": OCR_PIPELINE_VERSION,
                "ocr_pending": path_string in pending_paths,
            })
            if not same_source:
                record["text"] = ""
                record["indexed_at"] = indexed_at
            image_index[path_string] = record

        deleted_paths = [
            path
            for path in image_index
            if (path == str(base) or path.startswith(base_prefix))
            and path not in existing_paths
        ]
        for path in deleted_paths:
            del image_index[path]

        save_index()
        save_last_scan(base)
        total = len(image_index)

    _invalidate_search_cache()
    if progress_callback:
        progress_callback({
            "phase": "ready",
            "folder": str(base),
            "folders": folder_count,
            "total_files": len(found),
            "total_pending": total_pending,
            "scanned": 0,
            "remaining": total_pending,
        })
        progress_callback({
            "phase": "scanning",
            "folder": str(base),
            "folders": folder_count,
            "total_files": len(found),
            "total_pending": total_pending,
            "scanned": 0,
            "remaining": total_pending,
        })

    def store_word_boxes(
        path_string: str, modified: float, size_bytes: int, words: list
    ):
        if not words:
            return
        cache_file = _word_box_cache_file(Path(path_string))
        try:
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            temporary_file = cache_file.with_suffix(".tmp")
            with temporary_file.open("w", encoding="utf-8") as handle:
                json.dump(
                    {
                        "modified": modified,
                        "size_bytes": size_bytes,
                        "ocr_pipeline_version": OCR_PIPELINE_VERSION,
                        "words": words,
                    },
                    handle,
                    ensure_ascii=True,
                    separators=(",", ":"),
                )
            os.replace(temporary_file, cache_file)
        except OSError:
            pass

    cpu_count = os.cpu_count() or 4
    worker_count = max(1, min(4, cpu_count))
    scanned = 0
    completed_since_save = 0

    def report_progress(count: int = 1):
        nonlocal scanned
        scanned += count
        if progress_callback:
            progress_callback({
                "phase": "scanning",
                "folder": str(base),
                "folders": folder_count,
                "total_files": len(found),
                "total_pending": total_pending,
                "scanned": scanned,
                "remaining": max(0, total_pending - scanned),
            })

    image_pending = [
        item for item in pending if item[0].suffix.casefold() in IMAGE_EXTENSIONS
    ]
    pdf_pending = [
        item for item in pending if item[0].suffix.casefold() == ".pdf"
    ]

    reported_images = 0

    def report_image_progress(completed: int):
        nonlocal reported_images
        report_progress(completed - reported_images)
        reported_images = completed

    image_errors = []

    def store_ocr_result(entry, result, *, pending_after=False):
        nonlocal completed_since_save
        _, path_string, modified, size_bytes = entry
        text, words = result
        is_image_file = Path(path_string).suffix.casefold() in IMAGE_EXTENSIONS
        if is_image_file and not text.strip():
            image_errors.append(Path(path_string).name)
            # An empty result is not a searchable index. Retry on a later scan
            # in case the failure was transient.
            pending_after = True
        store_word_boxes(path_string, modified, size_bytes, words)
        with index_lock:
            record = image_index.get(path_string)
            if (
                record is not None
                and record.get("modified") == modified
                and record.get("size_bytes") == size_bytes
            ):
                record["text"] = text
                record["ocr_pending"] = pending_after
                record["indexed_at"] = datetime.now().isoformat(timespec="seconds")
                completed_since_save += 1
                if completed_since_save % 50 == 0:
                    save_index()
        _invalidate_search_cache()

    ocr_batch(
        image_pending,
        progress_callback=report_image_progress,
        result_callback=store_ocr_result,
        retain_results=False,
    )
    if image_pending and not OCR_AVAILABLE:
        image_errors.extend(entry[0].name for entry in image_pending)
    pdf_errors = []
    pdf_pending_by_path = {entry[1]: entry for entry in pdf_pending}

    def process_pdf(entry):
        path, path_string, _, _ = entry
        try:
            return path_string, extract_pdf_text(path), False
        except (OSError, RuntimeError, ValueError, pymupdf.FileDataError):
            return path_string, "", True

    with ThreadPoolExecutor(
        max_workers=min(worker_count, max(1, len(pdf_pending)))
    ) as executor:
        futures = [executor.submit(process_pdf, entry) for entry in pdf_pending]
        for future in as_completed(futures):
            path_string, text, failed = future.result()
            store_ocr_result(
                pdf_pending_by_path[path_string],
                (text, []),
                pending_after=failed,
            )
            if failed:
                pdf_errors.append(Path(path_string).name)
            report_progress()

    with index_lock:
        save_index()
        total = len(image_index)

    _invalidate_search_cache()
    return {
        "found": len(found),
        "pending": total_pending,
        "indexed": scanned,
        "skipped": len(found) - total_pending,
        "folders": folder_count,
        "total": total,
        "workers": worker_count,
        "pdf_errors": pdf_errors,
        "image_errors": image_errors,
    }
# Home page
@app.get("/")
def home():
    return FileResponse(APP_DIR / "static" / "index.html")


# Status
@app.get("/api/status")
def status():
    with index_lock:
        total = len(image_index)
    settings = {}
    try:
        with _settings_cache_path().open("r", encoding="utf-8") as settings_file:
            settings = json.load(settings_file)
    except (OSError, ValueError, TypeError):
        pass
    return {
        "ocr_available": OCR_AVAILABLE,
        "ocr_error": OCR_ERROR,
        "indexed_images": total,
        "last_scan_folder": settings.get("last_scan_folder"),
        "last_scan_time": settings.get("last_scan_time"),
    }

# Folder picker
@app.get("/api/select-folder")
def select_folder():
    if tk is None or filedialog is None:
        return {
            "ok": False,
            "error": "Folder picker is not available.",
        }
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        folder = filedialog.askdirectory(
            title="Select folder to scan"
        )
    finally:
        root.destroy()
    if folder:
        return {
            "ok": True,
            "folder": folder,
        }
    return {
        "ok": False,
        "cancelled": True,
    }

# Scan API
class ScanRequest(BaseModel):
    folder: str
    force_ocr: bool = False


@app.post("/api/scan")
def scan(req: ScanRequest):
    try:
        result = scan_folder(
            req.folder,
            req.force_ocr
        )
        return {
            "ok": True,
            **result,
        }
    except ValueError as e:
        return {
            "ok": False,
            "error": str(e),
        }
    except Exception as e:
        return {
            "ok": False,
            "error": f"Scan failed: {e}",
        }


# Search API
@app.get("/api/search")
def search(
    q: Annotated[str, Query(description="Text/number to search")] = "",
    folder: Optional[str] = None,
    field: Annotated[
        str,
        Query(pattern="^(all|name|year|number|date)$"),
    ] = "all",
    sort: Annotated[
        str,
        Query(pattern="^(relevance|name|newest|oldest)$"),
    ] = "relevance",
    date_from: Annotated[
        Optional[str], Query(description="YYYY-MM-DD lower bound")
    ] = None,
    date_to: Annotated[
        Optional[str], Query(description="YYYY-MM-DD upper bound")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
):
    q = q.strip()
    folder_prefix = str(Path(folder).expanduser().resolve()) if folder else None

    try:
        clauses = _parse_search_query(q)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    terms = [
        word
        for clause in clauses
        for value, _ in clause
        for word in _query_terms(value)
    ]

    rows = _searchable_rows()
    if folder_prefix:
        folder_path = folder_prefix + os.sep
        rows = [
            row
            for row in rows
            if row.path == folder_prefix or row.path.startswith(folder_path)
        ]
    if date_from:
        rows = [row for row in rows if row.date >= date_from.strip()]
    if date_to:
        rows = [row for row in rows if row.date <= date_to.strip()]

    matched = []
    if clauses:
        scored = []
        for row in rows:
            clause_scores = [
                score
                for clause in clauses
                if (score := _score_query_clause(row, clause, field)) is not None
            ]
            if clause_scores:
                scored.append((max(clause_scores), row))

        scored_paths = {row.path for _, row in scored}
        fuzzy = []
        for row in rows:
            if row.path in scored_paths:
                continue
            clause_scores = [
                score
                for clause in clauses
                if (
                    score := _score_query_clause(
                        row, clause, field, fuzzy=True
                    )
                ) is not None
            ]
            if clause_scores:
                fuzzy.append((max(clause_scores), row))

        relaxed = []
        has_explicit_syntax = bool(
            re.search(r'"|\b(?:AND|OR)\b', q, re.IGNORECASE)
        )
        if not has_explicit_syntax and len(terms) > 1:
            already_matched = scored_paths | {row.path for _, row in fuzzy}
            for row in rows:
                if row.path in already_matched:
                    continue
                partial = [
                    score
                    for term in terms
                    if (
                        score := _score_query_clause(
                            row, [(term, False)], field
                        )
                    ) is not None
                ]
                if partial:
                    relaxed.append((sum(partial), row))

        tiers = (
            [(2, score, row) for score, row in scored]
            + [(1, score, row) for score, row in fuzzy]
            + [(0, score, row) for score, row in relaxed]
        )
        matched = sorted(tiers, key=lambda item: (item[0], item[1]), reverse=True)
        if sort == "newest":
            matched.sort(key=lambda item: (-item[2].modified, item[2].filename))
        elif sort == "oldest":
            matched.sort(key=lambda item: (item[2].modified, item[2].filename))
        elif sort == "name":
            matched.sort(key=lambda item: item[2].filename)
        else:
            matched.sort(key=lambda item: (-item[0], -item[1], item[2].filename))
        rows = [row for _, _, row in matched]
    elif sort == "newest":
        rows = sorted(rows, key=lambda row: (-row.modified, row.filename))
    elif sort == "oldest":
        rows = sorted(rows, key=lambda row: (row.modified, row.filename))

    total = len(rows)
    results = []
    for row in rows[:limit]:
        record = dict(row.record)
        if terms:
            record["snippet"] = _snippet(row, terms, "")
        results.append(record)

    return {
        "count": total,
        "results": results,
    }
@app.get("/api/clear-index")
def clear_index_api():
    clear_index()
    return {
        "ok": True,
        "cleared": True,
    }



# Image view
@app.get("/api/image")
def get_image(path: str):
    p = Path(path)
    if not p.exists() or not is_image(p):
        return {"error": "Image not found"}
    return FileResponse(p)


# Image word boxes (highlight)
@app.get("/api/words")
def get_words(path: str):
    return {
        "path": path,
        "words": load_word_boxes(path),
    }


# Static files
# The native PyQt6 client does not need the legacy browser assets. Keep the
# API importable for compatibility when those assets are not packaged.
STATIC_DIR = APP_DIR / "static"
if STATIC_DIR.exists():
    app.mount(
        "/static",
        StaticFiles(directory=STATIC_DIR),
        name="static",
    )
