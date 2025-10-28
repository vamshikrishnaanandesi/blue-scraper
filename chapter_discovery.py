"""Chapter discovery and URL generation for bato.to."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import List, Optional

import requests

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36"
}

@dataclass
class Chapter:
    """Represents a manga chapter with its ID, number and metadata."""
    chapter_id: str  # the numeric ID in the URL (e.g., "1680643")
    chapter_num: float  # the chapter number (e.g., 45.5)
    volume: Optional[str] = None  # volume number if available
    title: Optional[str] = None  # chapter title if available
    lang: str = "en"  # language code

    def get_url(self, series_id: str) -> str:
        """Generate the full chapter URL given the series ID."""
        vol = f"vol_{self.volume}_" if self.volume else ""
        ch = f"ch_{self.chapter_num}".rstrip('.0')  # remove .0 for whole numbers
        return f"https://bato.si/title/{series_id}/{self.chapter_id}-{vol}{ch}"

    @property
    def display_name(self) -> str:
        """Get a human-readable chapter name including volume and title."""
        parts = []
        if self.volume:
            parts.append(f"Volume {self.volume}")
        parts.append(f"Chapter {self.chapter_num}")
        if self.title:
            parts.append(f"- {self.title}")
        return " ".join(parts)


def get_chapters_from_series(series_id: str, session: Optional[requests.Session] = None) -> List[Chapter]:
    """Fetch the series page and extract chapter information.
    
    Args:
        series_id: The series ID (e.g., "86663-en-grand-blue-dreaming-official")
        session: Optional requests session to use
    
    Returns:
        List of Chapter objects with IDs and numbers.
    """
    s = session or requests.Session()
    url = f"https://bato.si/title/{series_id}"
    r = s.get(url, headers=DEFAULT_HEADERS, timeout=20)
    r.raise_for_status()

    # Find the chapter list data in the page
    # Usually embedded as JSON in a script tag or data attribute
    chapters = []
    
    # Look for chapter data in scripts
    script_pattern = re.compile(r'window\.__DATA__\s*=\s*({[^}]+})')
    json_pattern = re.compile(r'"chapters":\s*(\[[^\]]+\])')
    
    # First try script tags
    for match in script_pattern.finditer(r.text):
        try:
            data = match.group(1)
            if '"chapters"' in data:
                for m in json_pattern.finditer(data):
                    try:
                        chaps = json.loads(m.group(1))
                        for c in chaps:
                            if isinstance(c, dict) and 'id' in c:
                                ch_num = float(c.get('number', 0))
                                vol = str(c.get('volume', '')).strip() or None
                                title = c.get('title', '').strip() or None
                                lang = c.get('lang', 'en')
                                chapters.append(Chapter(
                                    chapter_id=str(c['id']),
                                    chapter_num=ch_num,
                                    volume=vol,
                                    title=title,
                                    lang=lang
                                ))
                    except (ValueError, json.JSONDecodeError):
                        continue
        except Exception:
            continue

    # If no chapters found, try extracting from hrefs
    if not chapters:
        href_pattern = re.compile(rf'/title/{series_id}/(\d+)-(?:vol_(\d+)_)?ch_([0-9.]+)')
        for match in href_pattern.finditer(r.text):
            ch_id, vol, ch_num = match.groups()
            try:
                chapters.append(Chapter(
                    chapter_id=ch_id,
                    chapter_num=float(ch_num),
                    volume=vol
                ))
            except ValueError:
                continue

    # Sort by chapter number
    chapters.sort(key=lambda x: x.chapter_num)
    return chapters


def find_chapter_by_number(series_id: str, chapter_num: float, session: Optional[requests.Session] = None) -> Optional[Chapter]:
    """Find a specific chapter's info given its number.
    
    Args:
        series_id: The series ID (e.g., "86663-en-grand-blue-dreaming-official")
        chapter_num: The chapter number (e.g., 45.5)
        session: Optional requests session
    
    Returns:
        Chapter object if found, None otherwise
    """
    chapters = get_chapters_from_series(series_id, session)
    
    # First try to find exact match in current listing
    for chapter in chapters:
        if abs(chapter.chapter_num - chapter_num) < 0.01:  # handle float comparison
            return chapter
            
    # If chapter number is greater than any available chapter, fail fast
    if chapters and chapter_num > max(c.chapter_num for c in chapters):
        return None
        
    # Not found in current listing - try constructing the URL with probable IDs
    s = session or requests.Session()
    
    # Try a range of potential chapter IDs
    # Bato.to often uses IDs in this range for older chapters
    potential_ids = list(range(1680600, 1680700)) + list(range(3255000, 3255200))
    
    for ch_id in potential_ids:
        try:
            # Determine likely volume (rough estimate)
            vol = str(max(1, int(chapter_num // 4)))
            chapter = Chapter(
                chapter_id=str(ch_id),
                chapter_num=chapter_num,
                volume=vol
            )
            # Verify the chapter exists by making a HEAD request
            url = chapter.get_url(series_id)
            r = s.head(url, headers=DEFAULT_HEADERS, allow_redirects=True, timeout=5)
            if r.status_code == 200:
                return chapter
        except Exception:
            continue

    # Not found - prepare helpful error message
    available = sorted(set(c.chapter_num for c in chapters))
    closest = min(available, key=lambda x: abs(x - chapter_num))

    msg = [f"Chapter {chapter_num} not found."]
    if len(available) > 0:
        msg.append(f"Closest chapter: {closest}")
        # Show range of available chapters
        msg.append(f"Available range: {min(available)} - {max(available)}")
        # Show nearby chapters
        nearby = sorted(x for x in available if abs(x - chapter_num) <= 5)
        if nearby:
            msg.append(f"Nearby chapters: {', '.join(map(str, nearby))}")

    raise RuntimeError('\n'.join(msg))


def get_chapter_url(series_id: str, chapter_num: float, session: Optional[requests.Session] = None) -> str:
    """Get the full URL for a chapter given its number.
    
    Args:
        series_id: The series ID (e.g., "86663-en-grand-blue-dreaming-official")
        chapter_num: The chapter number (e.g., 45.5)
        session: Optional requests session
    
    Returns:
        Full chapter URL
    
    Raises:
        RuntimeError if chapter not found
    """
    chapter = find_chapter_by_number(series_id, chapter_num, session)
    if not chapter:
        raise RuntimeError(f"Chapter {chapter_num} not found in series {series_id}")
    return chapter.get_url(series_id)