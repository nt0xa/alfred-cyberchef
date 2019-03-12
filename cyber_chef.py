#!/usr/bin/python
# encoding: utf-8

import sys
import base64
import re

from workflow import Workflow3, web, ICON_WARNING, ICON_NOTE, ICON_INFO


log = None
RECIPE_RE = re.compile(r'^(?P<recipe>[a-zA-Z0-9_\.]+)(?P<args>\(.*?\))?[ ]?')


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
            wf.add_item(title=recipes[item]['title'],
                        subtitle=recipes[item]['category'],
                        autocomplete=item)
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
