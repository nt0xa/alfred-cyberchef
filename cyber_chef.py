#!/usr/bin/python
# encoding: utf-8

import os
import sys
import base64
import re

from workflow import Workflow3, web, ICON_WARNING, ICON_NOTE, ICON_INFO


log = None
RECIPE_RE = re.compile(r'^(?P<recipe>[a-zA-Z0-9_\.]+)(?P<args>\(.*?\))?[ ]?')

icons_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'icons')
ICON_ABC = os.path.join(icons_dir, 'abc.png')
ICON_CALCULATOR = os.path.join(icons_dir, 'calculator.png')
ICON_TOOLS = os.path.join(icons_dir, 'construction-and-tools.png')
ICON_DIGITAL = os.path.join(icons_dir, 'digital.png')
ICON_DOWN_ARROW = os.path.join(icons_dir, 'down-arrow.png')
ICON_EARTH = os.path.join(icons_dir, 'earth-grid.png')
ICON_FOLDER = os.path.join(icons_dir, 'folder.png')
ICON_MAGNIFIER = os.path.join(icons_dir, 'magnifying-glass.png')
ICON_LOCK = os.path.join(icons_dir, 'padlock.png')
ICON_TIME = os.path.join(icons_dir, 'time.png')
ICON_CODE = os.path.join(icons_dir, 'coding.png')
ICON_CERT = os.path.join(icons_dir, 'contract.png')
ICONS = {
    'networking': ICON_EARTH,
    'language': ICON_ABC,
    'encryption / encoding': ICON_LOCK,
    'code tidy': ICON_CODE,
    'data format': ICON_DIGITAL,
    'public key': ICON_CERT,
    'extractors': ICON_DOWN_ARROW,
    'forensics': ICON_MAGNIFIER,
    'utils': ICON_TOOLS,
    'date / time': ICON_TIME,
    'arithmetic / logic': ICON_CALCULATOR,
}


def get_recipes():
    url = ('https://raw.githubusercontent.com/gchq/CyberChef' +
           '/master/src/core/config/Categories.json')
    r = web.get(url)

    r.raise_for_status()

    categories = r.json()

    recipes = dict()

    for category in categories:
        for op in category['ops']:
            key = op.replace(' ', '_')
            recipes[key] = dict(category=category['name'], title=op)

    return recipes


def build_url(recipe, args, data):
    url = 'https://gchq.github.io/CyberChef/#recipe=%s%s&input=%s'
    data = base64.urlsafe_b64encode(data).replace('=', '')
    result = url % (recipe, args if args else '()', data)
    return result


def main(wf):
    # Handle updates
    if wf.update_available:
        wf.add_item(title='New version available',
                    subtitle='Action this item to install the update',
                    autocomplete='workflow:update',
                    icon=ICON_INFO)

    query = None

    if len(wf.args):
        query = wf.args[0]

    # Get recipes once a week
    recipes = wf.cached_data('recipes', get_recipes, max_age=604800)

    matches = RECIPE_RE.match(query)

    if matches and matches.group('recipe') not in recipes:
        items = wf.filter(query, recipes.keys())

        if not items:
            wf.add_item('No matches', icon=ICON_WARNING)

        for item in items:
            category = recipes[item]['category'].lower()
            icon = ICONS[category] if category in ICONS else None
            wf.add_item(title=recipes[item]['title'],
                        subtitle=category,
                        autocomplete=item,
                        icon=icon)
    else:
        recipe = matches.group('recipe')
        args = matches.group('args')
        data = RECIPE_RE.sub('', query)

        if data:
            wf.add_item('Open on CyberChef',
                        valid=True,
                        arg=build_url(recipe, args, data))
        else:
            wf.add_item('Enter data to process', icon=ICON_NOTE)

    wf.send_feedback()


if __name__ == '__main__':
    wf = Workflow3(update_settings={
        'github_slug': 'russtone/alfred-cyberchef',
        'frequency': 7,
    })
    log = wf.logger
    sys.exit(wf.run(main))
