import os
import sys
import string
import re
import json
import time

from enum import Enum, Flag, auto
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, TypeVar, Tuple, Match, Any, cast
from pathlib import Path


class ModKey(Enum):
    cmd = "cmd"
    ctrl = "ctrl"
    alt = "alt"
    shift = "shift"
    fn = "fn"


@dataclass
class ModItem:
    subtitle: str
    valid: bool = False
    arg: Optional[str] = None


@dataclass
class Text:
    copy: str
    largetype: Optional[str] = None


class IconType(Enum):
    filetype = "filetype"
    fileicon = "fileicon"


class ItemType(Enum):
    default = "default"
    file = "file"
    file_skipcheck = "file:skipcheck"


ICON_ROOT = Path("/System/Library/CoreServices/CoreTypes.bundle/Contents/Resources")


@dataclass
class Icon:
    path: str
    type: Optional[IconType] = None

    @classmethod
    def system(cls, name: str):
        return cls(path=str(ICON_ROOT / name))


@dataclass
class Item:
    # Title shown in Alfred
    title: str

    # Subtitle shown in Alfred
    subtitle: str = ""

    # Subtitles shown when modifier (⌘, ⌥ etc.) is pressed.
    mods: Dict[ModKey, ModItem] = field(default_factory=dict)

    # Argument passed by Alfred as {query} when item is actioned
    arg: Optional[str] = None

    # Text expanded in Alfred when item is TAB-bed
    autocomplete: Optional[str] = None

    # Whether or not item can be actioned
    valid: bool = False

    # Used by Alfred to remember/sort items
    uid: Optional[str] = None

    # Filename of icon to use
    icon: Optional[Icon] = None

    # Result type. Currently only 'file' is supported
    # (by Alfred). This will tell Alfred to enable file actions for
    # this item.
    type: Optional[ItemType] = None

    # Text to be displayed in Alfred's large text box if user presses ⌘+L on item.
    text: Optional[Text] = None

    # URL to be displayed using Alfred's Quick Look feature
    # (tapping SHIFT or ⌘+Y on a result).
    quicklookurl: Optional[str] = None


def todict(obj):
    if isinstance(obj, dict):
        data = {}
        for (k, v) in obj.items():
            if hasattr(k, "value"):
                k = k.value
            data[k] = todict(v)
        return data
    elif hasattr(obj, "__iter__") and not isinstance(obj, str):
        return [todict(v) for v in obj]
    elif hasattr(obj, "__dict__"):
        data = {
            key: todict(value)
            for key, value in obj.__dict__.items()
            if value is not None and not callable(value) and not key.startswith("_")
        }
        return data
    else:
        return obj


class JsonEncoder(json.JSONEncoder):
    def default(self, o):
        return todict(o)


@dataclass
class Feedback:
    items: List[Item] = field(default_factory=list)

    def prepend_item(self, item: Item):
        self.items.insert(0, item)

    def append_item(self, item: Item):
        self.items.append(item)

    def to_json(self) -> str:
        return JsonEncoder().encode(self)

    def is_empty(self) -> bool:
        return len(self.items) == 0

    def send(self):
        sys.stdout.write(self.to_json())
        sys.stdout.flush()

    def error(self, message: str):
        self.items = [Item(title=message, icon=Icon.system("AlertStopIcon.icns"))]
        self.send()


class MatchOn(Flag):
    # Match items that start with `query`
    STARTSWITH = auto()

    # Match items whose capital letters start with `query`
    CAPITALS = auto()

    # Match items with a component "word" that matches `query`
    ATOM = auto()

    # Match items whose initials (based on atoms) start with `query`
    INITIALS_STARTSWITH = auto()

    # Match items whose initials (based on atoms) contain `query`
    INITIALS_CONTAINS = auto()

    # Match items if `query` is a substring
    SUBSTRING = auto()

    # Match items if all characters in `query` appear in the item in order
    ALLCHARS = auto()

    INITIALS = INITIALS_STARTSWITH | INITIALS_CONTAINS

    ALL = STARTSWITH | CAPITALS | ATOM | INITIALS | SUBSTRING | ALLCHARS


ListItem = TypeVar("ListItem")


def filter_items(
    items: List[ListItem],
    query: str,
    key: Callable[[ListItem], str],
    max_results: Optional[int] = None,
    ascending: bool = False,
    match_on: MatchOn = MatchOn.ALL,
) -> List[ListItem]:
    if not query:
        return items

    # Remove preceding/trailing spaces
    query = query.strip()

    results = []

    for item in items:
        skip = False
        score = 0.0
        words = [s.strip() for s in query.split(" ")]
        value = key(item).strip()

        if not value:
            continue

        for word in words:
            if not word:
                continue

            s, rule = _filter_item(
                value,
                word,
                match_on,
            )

            if not s:  # Skip items that don't match part of the query
                skip = True

            score += s

        if score:
            # use "reversed" `score` (i.e. highest becomes lowest) and
            # `value` as sort key. This means items with the same score
            # will be sorted in alphabetical not reverse alphabetical order
            results.append(((100.0 / score, value.lower(), score), item))

    results.sort(reverse=ascending)

    filtered_items = [r[1] for r in results]

    if max_results:
        filtered_items = filtered_items[:max_results]

    return filtered_items


_INITIALS = string.ascii_uppercase + string.digits
_split_on_delimiters = re.compile("[^a-zA-Z0-9]").split


def _filter_item(
    value: str, query: str, match_on: MatchOn
) -> Tuple[float, Optional[MatchOn]]:
    query = query.lower()

    # pre-filter any items that do not contain all characters
    # of `query` to save on running several more expensive tests
    if set(query) > set(value.lower()):
        return (0, None)

    # item starts with query
    if match_on & MatchOn.STARTSWITH and value.startswith(query):
        score = 100.0 - (len(value) / len(query))
        return (score, MatchOn.STARTSWITH)

    # query matches capitalised letters in item
    if match_on & MatchOn.CAPITALS:
        initials = "".join([c for c in value if c in _INITIALS])
        if initials.lower().startswith(query):
            score = 100.0 - (len(initials) / len(query))
            return (score, MatchOn.CAPITALS)

    # split the item into "atoms", i.e. words separated by
    # spaces or other non-word characters
    if (
        match_on & MatchOn.ATOM
        or match_on & MatchOn.INITIALS_CONTAINS
        or match_on & MatchOn.INITIALS_STARTSWITH
    ):
        atoms = [s.lower() for s in _split_on_delimiters(value)]
        initials = "".join([s[0] for s in atoms if s])

    # is `query` one of the atoms in item?
    # similar to substring, but scores more highly, as it's
    # a word within the item
    if match_on & MatchOn.ATOM:
        if query in atoms:
            score = 100.0 - (len(value) / len(query))
            return (score, MatchOn.ATOM)

    # `query` matches start (or all) of the initials of the
    # atoms, e.g. `himym` matches "How I Met Your Mother"
    # *and* "how i met your mother" (the `capitals` rule only
    # matches the former)
    elif match_on & MatchOn.INITIALS_STARTSWITH and initials.startswith(query):
        score = 100.0 - (len(initials) / len(query))
        return (score, MatchOn.INITIALS_STARTSWITH)

    # `query` is a substring of initials, e.g. `doh` matches
    # "The Dukes of Hazzard"
    elif match_on & MatchOn.INITIALS_CONTAINS and query in initials:
        score = 95.0 - (len(initials) / len(query))
        return (score, MatchOn.INITIALS_CONTAINS)

    # `query` is a substring of item
    if match_on & MatchOn.SUBSTRING and query in value.lower():
        score = 90.0 - (len(value) / len(query))
        return (score, MatchOn.SUBSTRING)

    # finally, assign a score based on how close together the
    # characters in `query` are in item.
    if match_on & MatchOn.ALLCHARS:
        search = _search_for_query(query)
        match = search(value)
        if match:
            score = 100.0 / ((1 + match.start()) * (match.end() - match.start() + 1))

            return (score, MatchOn.ALLCHARS)

    return (0, None)


_SEARCH_PATTERN_CACHE: Dict[str, Callable[[str, int, int], Optional[Match[str]]]] = {}


def _search_for_query(query: str):
    if query in _SEARCH_PATTERN_CACHE:
        return _SEARCH_PATTERN_CACHE[query]

    patterns = []

    for c in query:
        patterns.append(".*?{0}".format(re.escape(c)))

    pattern = "".join(patterns)
    search = re.compile(pattern, re.IGNORECASE).search

    _SEARCH_PATTERN_CACHE[query] = search
    return search


CACHE_DIR = Path(cast(str, os.getenv("alfred_workflow_cache")))

if not CACHE_DIR.exists():
    CACHE_DIR.mkdir()

def cached_data(key: str, data_func=None, max_age=60):
    cache_path: Path = CACHE_DIR / key

    age = time.time() - cache_path.stat().st_mtime if cache_path.exists() else 0

    if (age < max_age or max_age == 0) and cache_path.exists():
        with open(cache_path, "rb") as f:
            return json.load(f)

    if not data_func:
        return None

    data = data_func()

    if data is None and cache_path.exists():
        cache_path.unlink()
        return None

    with open(cache_path, "w") as f:
        json.dump(data, f)

    return data


if __name__ == "__main__":
    item = Item(
        title="test",
        subtitle="test",
        arg="Hello!<World>!",
        mods={ModKey.cmd: ModItem(subtitle="test")},
    )
    feedback = Feedback()
    feedback.append_item(item)
    print(feedback.to_json())
