---
name: Bug Report
about: Report a misbehaviour in existing functionality
title: ''
labels: bug
assignees: ''

---

**Before filing a bug report...**
* [ ] I have checked [the FAQ](https://ssokolow.com/quicktile/faq.html)
* [ ] I have [searched for existing open bugs](https://github.com/ssokolow/quicktile/issues)
* [ ] I have confirmed the bug exists on the [latest upstream version](https://github.com/ssokolow/quicktile/archive/refs/heads/master.zip) of QuickTile ([Setup instructions](https://ssokolow.com/quicktile/installation.html))

## Bug Summary
A clear and concise description of what the bug is

## Reproduction Instructions...
1. Focus a window with characteristic X
2. Trigger tiling command Y
3. ...then trigger tiling command Z.

## Debug Output:

```
Run QuickTile with the `--debug` option (eg. `./quicktile.sh --debug`) and cause the bug.

Then paste the resulting console output here.

IMPORTANT: If cutting the output down, retain the header which looks like this
so I can quickly reproduce the conditions needed to trigger the bug:

DEBUG: Starting QuickTile [version] on [$XDG_CURRENT_DESKTOP] under Python [version]
DEBUG: Host OS is [uname -a]
DEBUG: Host distro is [lsb_release -a]
```

If you are running a custom window manager, please include its name and the output from running it with `--version` here. (eg. `openbox --version`)

## Traceback:
If you're reporting a bug that resulted in the "A programming error has been detected during the execution of this program." dialog, please attach the traceback from the `Details...` button to your bug report.
