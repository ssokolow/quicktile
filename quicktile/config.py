"""Configuration parsing code"""

import logging, os
from configparser import ConfigParser

from typing import Dict, Union

#: Location for config files (determined at runtime).
XDG_CONFIG_DIR = os.environ.get('XDG_CONFIG_HOME',
                                os.path.expanduser('~/.config'))

#: MyPy type alias for fields loaded from config files
CfgDict = Dict[str, Union[str, int, float, bool, None]]  # pylint:disable=C0103

#: Default content for the configuration file
#:
#: .. todo:: Figure out a way to show :data:`DEFAULTS` documentation but with
#:    the structure pretty-printed.
DEFAULTS: Dict[str, CfgDict] = {
    'general': {
        # Use Ctrl+Alt as the default base for key combinations
        'ModMask': '<Ctrl><Alt>',
        'MovementsWrap': True,
        'ColumnCount': 3,
        'MarginX_Percent': 0,
        'MarginY_Percent': 0,
    },
    'keys': {
        "KP_Enter": "monitor-switch",
        "KP_0": "maximize",
        "KP_1": "bottom-left",
        "KP_2": "bottom",
        "KP_3": "bottom-right",
        "KP_4": "left",
        "KP_5": "center",
        "KP_6": "right",
        "KP_7": "top-left",
        "KP_8": "top",
        "KP_9": "top-right",
        "<Shift>KP_1": "move-to-bottom-left",
        "<Shift>KP_2": "move-to-bottom",
        "<Shift>KP_3": "move-to-bottom-right",
        "<Shift>KP_4": "move-to-left",
        "<Shift>KP_5": "move-to-center",
        "<Shift>KP_6": "move-to-right",
        "<Shift>KP_7": "move-to-top-left",
        "<Shift>KP_8": "move-to-top",
        "<Shift>KP_9": "move-to-top-right",
        "V": "vertical-maximize",
        "H": "horizontal-maximize",
        "C": "move-to-center",
    }
}

#: Used for resolving certain keysyms
#:
#: .. todo:: Figure out how to replace :data:`KEYLOOKUP` with a fallback that
#:      uses something in `Gtk <http://lazka.github.io/pgi-docs/Gtk-3.0/>`_ or
#:      ``python-xlib`` to look up the keysym from the character it types.
KEYLOOKUP = {
    ',': 'comma',
    '.': 'period',
    '+': 'plus',
    '-': 'minus',
}


def load_config(path) -> ConfigParser:
    """Load the config file from the given path, applying fixes as needed.
    If it does not exist, create it from the configuration defaults.

    :param path: The path to load or initialize.

    :raises TypeError: Raised if the keys or values in the :ref:`[keys]`
        section of the configuration file or what they resolve to via
        :any:`KEYLOOKUP` are not :any:`str` instances.

    .. todo:: Refactor config parsing. It's an ugly blob.
    """
    first_run = not os.path.exists(path)

    config = ConfigParser(interpolation=None)

    # Make keys case-sensitive because keysyms must be
    #
    # (``type: ignore`` to squash a false positive for something the Python 3.x
    # documentation specifically *recommends* over using RawConfigParser)
    config.optionxform = str  # type: ignore

    config.read(path)
    dirty = False

    if not config.has_section('general'):
        config.add_section('general')
        # Change this if you make backwards-incompatible changes to the
        # section and key naming in the config file.
        config.set('general', 'cfg_schema', '1')
        dirty = True

    # Transparently update the config to add missing keys
    for key, val in DEFAULTS['general'].items():
        if not config.has_option('general', key):
            config.set('general', key, str(val))
            dirty = True

    mk_raw = config.get('general', 'ModMask')
    modkeys = mk_raw.strip()  # pylint: disable=E1101
    if ' ' in modkeys and '<' not in modkeys:
        modkeys = '<%s>' % '><'.join(modkeys.split())
        logging.info("Updating modkeys format:\n %r --> %r", mk_raw, modkeys)
        config.set('general', 'ModMask', modkeys)
        dirty = True

    # Either load the keybindings or use and save the defaults
    if config.has_section('keys'):
        keymap: CfgDict = dict(config.items('keys'))
    else:
        keymap = DEFAULTS['keys']
        config.add_section('keys')
        for key, cmd in keymap.items():
            if not isinstance(key, str):  # pragma: nobranch
                raise TypeError(  # pragma: nocover
                    "Hotkey name must be a str: {!r}".format(key))
            if not isinstance(cmd, str):  # pragma: nobranch
                raise TypeError(  # pragma: nocover
                    "Command name must be a str: {!r}".format(cmd))
            config.set('keys', key, cmd)
        dirty = True

    # Migrate from the deprecated syntax for punctuation keysyms
    for key in keymap:
        # Look up unrecognized shortkeys in a hardcoded dict and
        # replace with valid names like ',' -> 'comma'
        if key in KEYLOOKUP:
            cmd = keymap[key]
            if not isinstance(cmd, str):  # pragma: nobranch
                raise TypeError(  # pragma: nocover
                    "Command name must be a str: {!r}".format(cmd))

            logging.warning("Updating config file from deprecated keybind "
                "syntax:\n\t%r --> %r", key, KEYLOOKUP[key])
            config.remove_option('keys', key)
            config.set('keys', KEYLOOKUP[key], cmd)
            dirty = True

    # Automatically update the old 'middle' command to 'center'
    for key in keymap:
        if keymap[key] == 'middle':
            keymap[key] = cmd = 'center'
            logging.warning("Updating old command in config file:"
                    "\n\tmiddle --> center")
            config.set('keys', key, cmd)
            dirty = True

    if dirty:
        with open(path, 'w') as cfg_file:
            config.write(cfg_file)
        if first_run:
            logging.info("Wrote default config file to %s", path)

    return config
