import sys
import re
import os
import urllib.request
import json
import base64

from pathlib import Path

from utils import Feedback, Item, Icon, filter_items, cached_data

RECIPE_RE = re.compile(r"^(?P<recipe>[a-zA-Z0-9_\.]+)(?P<args>\(.*?\))?[ ]?")

icons_dir = Path(__file__).parent / "icons"

ICON_ABC = Icon(path=str(icons_dir / "abc.png"))
ICON_CALCULATOR = Icon(path=str(icons_dir / "calculator.png"))
ICON_CODE = Icon(path=str(icons_dir / "coding.png"))
ICON_TOOLS = Icon(path=str(icons_dir / "construction-and-tools.png"))
ICON_CERT = Icon(path=str(icons_dir / "contract.png"))
ICON_DIGITAL = Icon(path=str(icons_dir / "digital.png"))
ICON_DOWN_ARROW = Icon(path=str(icons_dir / "down-arrow.png"))
ICON_EARTH = Icon(path=str(icons_dir / "earth-grid.png"))
ICON_FOLDER = Icon(path=str(icons_dir / "folder.png"))
ICON_MAGNIFIER = Icon(path=str(icons_dir / "magnifying-glass.png"))
ICON_LOCK = Icon(path=str(icons_dir / "padlock.png"))
ICON_TIME = Icon(path=str(icons_dir / "time.png"))


ICONS = {
    "networking": ICON_EARTH,
    "language": ICON_ABC,
    "encryption / encoding": ICON_LOCK,
    "code tidy": ICON_CODE,
    "data format": ICON_DIGITAL,
    "public key": ICON_CERT,
    "extractors": ICON_DOWN_ARROW,
    "forensics": ICON_MAGNIFIER,
    "utils": ICON_TOOLS,
    "date / time": ICON_TIME,
    "arithmetic / logic": ICON_CALCULATOR,
}


def get_recipes():
    url = (
        "https://raw.githubusercontent.com/gchq/CyberChef"
        + "/master/src/core/config/Categories.json"
    )
    req = urllib.request.Request(url)

    with urllib.request.urlopen(req) as f:
        res = json.load(f)

    recipes = {}

    for category in res:
        for op in category["ops"]:
            key = op.replace(" ", "_")
            recipes[key] = dict(category=category["name"], title=op)

    return recipes


def build_url(recipe, args, data):
    data = base64.urlsafe_b64encode(data.encode()).decode().replace("=", "")
    return f"recipe={recipe}{args if args else '()'}&input={data}"


def main(query):
    feedback = Feedback()

    # Get recipes once a week
    recipes = cached_data("recipes", get_recipes, max_age=3600 * 24 * 7)

    matches = RECIPE_RE.match(query)

    if matches and matches.group("recipe") not in recipes:
        items = filter_items(recipes.keys(), query, lambda x: x)

        if not items:
            feedback.append_item(
                Item(
                    title="No matches",
                )
            )

        for item in items:
            category = recipes[item]["category"].lower()
            icon = ICONS[category] if category in ICONS else None
            feedback.append_item(
                Item(
                    title=recipes[item]["title"],
                    subtitle=category,
                    autocomplete=item,
                    icon=icon,
                )
            )
    else:
        recipe = matches.group("recipe")
        args = matches.group("args")
        data = RECIPE_RE.sub("", query)

        if data:
            feedback.append_item(
                Item(
                    "Open on CyberChef",
                    valid=True,
                    arg=build_url(recipe, args, data),
                )
            )
        else:
            feedback.append_item(Item(title="Enter data to process"))

    feedback.send()


if __name__ == "__main__":
    main(sys.argv[1])
