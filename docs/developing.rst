Developer's Guide
=================

.. contents::
   :local:

.. todo:: Aside from the obvious factor that it exposes a lot of architectural
   cleanup that needs to be done, something about ``developing.rst`` feels
   sloppy to me. I think reading some O'Reilly books to examine how they're
   written might help me to figure out what's wrong.

Setting up a Development Environment
------------------------------------

It should be possible to develop QuickTile on any POSIX-compatible platform
with X11-based graphics. However, Linux is the only officially supported
option.

To ensure your changes get accepted as quickly as possible, please bear in mind
the :ref:`testing requirements <testing-quicktile>`.


On the operating system you intend to use for development:

1. Begin by cloning the QuickTile repository. either directly or from a fork
   you've made on GitHub:

   .. code-block:: sh

      git clone git@github.com:ssokolow/quicktile.git

2. Install the :ref:`runtime dependencies <Dependencies>`.

3. Install Xvfb, Openbox, and Zenity (eg. ``sudo apt install xvfb openbox
   zenity``) for the functional tests.

3. Either use the following command to install QuickTile's additional
   development-time dependencies, or manually install the dependencies listed
   therein:

   .. code-block:: sh

      pip3 install -r dev_requirements.txt

   These dependencies fall into one of two categories:

   * Source code verification (Ruff_ for static analysis and code style,
     MyPy_ for checking type hints, PyTest_ for test discovery, and
     `Coverage.py`_ for determining test coverage)
   * Documentation generation (Sphinx_, `sphinx-autodoc-typehints`_, and
     `sphinxcontrib-autoprogram`_)

4. If you intend to modify the illustrations or demonstratory animation, you
   will also require the following to regenerate the built files:

   * A POSIX-compatible environment (For tools such as :command:`find`)
   * `GNU Make`_ (to run the Makefiles used to automate the process)
   * Inkscape_ (to render the SVG sources to PNG)
   * OptiPNG_ and AdvanceCOMP_ (to optimize the illustrations)
   * ImageMagick_ (to combine the frames of the animation into an animated GIF)
   * Gifsicle_ (to optimize the animation)

5. Rely on the ``./quicktile.sh`` option for running QuickTile without
   installing it as described in :ref:`install_quicktile.sh`.

   This combination of full access to Git functionality and the ability to run
   the changed code without needing to install first provides for the simplest
   development environment, and makes it easy to remove the development version
   and revert to the release versions once you are finished.

Building Development Documentation
----------------------------------

QuickTile's documentation contains extensive TODO notes which are omitted from
release versions.

To enable inclusion of these development notes...

1. Uncomment ``todo_include_todos = True`` in :file:`docs/conf.py`
2. Run ``(cd docs; make html)``.
3. Your developer documentation should now exist in :file:`docs/_build/html/`.

The resulting API documentation will include in-line TODO annotations, as well
as a complete listing at the bottom of the :doc:`apidocs/index` page.

.. note:: If Sphinx fails to notice that part of the documentation should be
   rebuilt, a rebuild can be forced either by deleting the :file:`_build/html`
   directory or by running ``(cd docs; make html SPHINXOPTS=-E)`` instead.

   Generated documentation, such :doc:`cli` may also require deleting other
   files under ``_build`` but it is advised to delete individual files such as
   ``_build/doctrees/cli.doctree`` instead of the entire ``_build`` folder
   to avoid re-downloading the InterSphinx indexes, which could
   get you temporarily rate-limited.

There also exist TODO comments in the source code (usually ones that shouldn't
be seen as drawing attention away from the ones in the Sphinx docs) which can
be searched for by running the following command in the project root:

.. code-block:: sh

    grep -E 'XXX|TODO|FIXME' -nR *.py quicktile tests

Regenerating Documentation Graphics
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

To regenerate the illustrations, run the following command:

.. code-block:: sh

    (cd docs/diagrams; make) && (cd docs; make html)

To regenerate the animation, run the following command:

.. code-block:: sh

    (cd docs/animation; make) && (cd docs; make html)

**You only need to do this if you've modified the original SVG files.**

Documentation Privacy Policy
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Out of respect for user privacy and to make offline use of this documentation
as robust as possible, this website/manual makes no external HTTP requests.

To mitigate the risk of such requests slipping in through non-obvious means,
such as use of the Sphinx ``:math:`` role pulling in a CDN-hosted copy of
MathJax_, a `Content Security Policy`_ meta-tag has been added to the header of
the site template.

It is preferred that you check your browser's developer console for reports
of requests blocked by the :abbr:`CSP (Content Security Policy)` rules on the
relevant pages before submitting changes to the manual or docstrings.

.. _Content Security Policy: https://developer.mozilla.org/en-US/docs/Web/HTTP/CSP
.. _MathJax: https://www.mathjax.org/

High-Level QuickTile Architecture
---------------------------------

Quicktile is fundamentally built around a somewhat HTTP-like request-response
model. The user requests an action, QuickTile performs that action, and then it
goes back to waiting for another event.

Any state which needs to persist between these event handlers should be stored
as X11 window properties using the
:meth:`quicktile.wm.WindowManager.set_property` and
:meth:`quicktile.wm.WindowManager.get_property` methods.

.. todo:: Document the values that commands will be passed when called.

Quirks of the Codebase's Structure
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

* The :mod:`quicktile.__main__.main` function is currently responsible for
  gluing everything together.

* At the moment, due to an incomplete refactoring during the GTK+ 3 port, the
  :mod:`quicktile.keybinder` module is still structured as if optional, though
  it is now required for its role in managing the Xlib connection.

  Due to oddities in how the X11 protocol behaves when interacting with
  short-lived connections, you are likely to get strange and confusing bugs if
  the keybinder is not allowed to properly carry out its responsibility for
  integrating X11 into the QuickTile event loop.

  (Indeed, the bugs that still need to be rooted out of the QuickTile event loop
  stem from my not having properly rooted out bugs relating to X11 and
  short-lived applications.)

* At present, window management is split between the :mod:`quicktile.wm` and
  :mod:`quicktile.util` modules, with the former being concerned with
  communication with the outside world and the latter having temporarily become
  a grab-bag of everything that is so self-contained as to be easy to
  unit test.

* The :mod:`quicktile.commands` module also needs to be refactored as it
  currently contains the framework for registering and executing tiling
  commands and the shared setup code for them (lumped into a single class) as
  well as all of the commands themselves.

.. todo:: Figure out a way to get URLs working in Sphinx's Graphviz_ extension
   that doesn't break when the default CSS downscales the diagram to keep it
   fitting in the document and then diagram QuickTile's functional
   interdependencies.

Good Development Practice
-------------------------

Before making changes you intend to have merged back into QuickTile's
``master`` branch, please open a feature request on the `issue tracker`_ to
propose them. This will allow me to bring up any non-obvious design concerns
which might complicate, delay, or preclude my accepting your changes.

.. note:: Please bear in mind that QuickTile is still catching up after a
   decade of spotty maintenance and it may take time for your changes to get
   proper attention.

When working on QuickTile, please keep the following code-quality goals in
mind as, if you do not, then merging your changes may have to wait until I can
revise them:

* All function arguments should bear complete type annotations which pass
  MyPy's scrutiny and use of :any:`typing.Any` or ``# type: ignore`` must be
  approved on a case-by-case basis.
* All Ruff_ complaints must either be resolved or whitelisted.
  New whitelisting annotations must include comments
  justifying their presence, except in self-evident cases such as URLs in
  docstrings which exceed the line-length limit.
* All code within the ``quicktile`` package must have complete API
  documentation that renders through Sphinx to a standard consistent with
  existing documentation.
* doctests count as implicit API requirements and changes to them should not
  be made frivolously.
* The percentage of unit test coverage in the :mod:`quicktile.util` module
  should not decrease. (Enforcing this standard outside of that module will
  not be feasible until further refactoring and test harness work is
  completed.)

Once your changes are ready, the standard way to submit them is via `pull
request`_ against the ``master`` branch, as this will automatically trigger
a test run, as well as making it as simple as possible for me to examine and
accept them.

.. _testing-quicktile:

Testing Your Changes
--------------------

Testing Environment Concerns
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

As of this writing, QuickTile's current minimum compatibility target is Kubuntu
Linux 24.04 LTS. This may be broadened as the testing infrastructure is
modernized.

If this is not what you are running, I suggest using VirtualBox_ for
compatibility testing, as it is easy to set up and has support for virtual
machines with multiple monitors.

.. warning:: When installing VirtualBox, be sure to **not** install the Oracle
    VM VirtualBox Extension Pack, as it phones home and Oracle has been
    making large licensing demands of people who they believe to be using it
    commercially.
    `[1] <https://www.theregister.co.uk/2019/10/04/oracle_virtualbox_merula/>`_
    `[2] <https://www.reddit.com/r/sysadmin/comments/d1ttzp/oracle_is_going_after_companies_using_virtualbox/>`_

    Those using only VirtualBox packages provided by their Linux distribution's
    official package repositories should have no need to worry, but its absence
    can be confirmed by choosing :menuselection:`File --> Tools --> Extension
    Pack Manager` from the VirtualBox menu bar, and verifying that no
    extensions other than :guilabel:`VNC` are present.

    Should this prove too concerning, KVM-based solutions such as virt-manager_
    or `GNOME Boxes`_ should also serve equally well though I can give no
    advice on setting them up for multi-monitor support.

.. _GNOME Boxes: https://help.gnome.org/users/gnome-boxes/stable/
.. _virt-manager: https://virt-manager.org/
.. _VirtualBox: https://www.virtualbox.org/

For best results, configure your virtual desktop with the following characteristics:

1. Differently-sized monitors (Certain bugs in moving windows from monitor to
   monitor can only be triggered if one monitor is larger or smaller than
   another.)
2. Panels (taskbars and the like) on an edge where the monitors are adjacent
   but do not line up.

   Suppose you have a 1280x1024 monitor and a 1920x1080 monitor, and the tops
   are aligned. Place panels on the bottom, so that the reservation for the
   shorter monitor will also have to cover the dead space below it and has the
   best chance of triggering any dead-space-related bugs in the code for
   calculating usable regions.

.. note:: The following two behaviours are currently known bugs where a proper
   solution is blocked on reworking how window state is tracked and you don't
   need to worry that you've caused them:

   1. If a window is so far down or to the right that it would be outside the
      bounds of the destination monitor, QuickTile will refuse to honor a request to move it to that monitor to avoid the risk of your window manager allowing it to get lost off the edge of the desktop. This can block commands like ``monitor-switch``.
   2. If a window's top-left corner is within the bounds of the destination
      montiro, but its bottom-right corner extends beyond it, the window will
      be resized to fit, but it won't remember its old size if it's moved back
      to its original monitor.

Automated Testing
^^^^^^^^^^^^^^^^^

To run a complete set of all tests, please use
the following command from the root of the project:

.. code-block:: sh

    ./run_tests.sh

The following will be run:

* MyPy_ to check for violations of the type annotations.
* Ruff_ for basic static analysis and code style checking
* PyTest_ and doctest_ to run the unit tests (currently of limited scope)
* doctest_ to check for broken code examples in the API documentation
* Sphinx_'s ``make coverage`` to check documentation coverage
  (currently of questionable reliability)

In lieu of a proper functional test suite, please manually execute all tiling
commands which rely on code you've touched and watch for misbehaviour.

Semi-Automated Testing
^^^^^^^^^^^^^^^^^^^^^^

While QuickTile does not yet have a proper functional test suite, the
``test_functional.sh`` script can be used to quickly perform human testing of
most of the commands for both the CLI and D-Bus interfaces.

1. Open a free-floating terminal window which is not set to be always on top or
   on all desktops.
2. Run ``./test_functional.sh``
3. Follow the instructions

The script will temporarily make the terminal window always-on-top and
on-all-desktops, open a test window (FeatherPad by default), and then walk it
through a predefined sequence of QuickTile commands, with a one-second delay
between each.

The intended way to use it is to keep your eyes focused on the "Testing
[command name]..." messages in the terminal, while you confirm that the
movement you're seeing in your peripheral vision matches what it's claiming to
do.

Adding Yourself to the :file:`AUTHORS` List
-------------------------------------------

When making a contribution, please also add yourself to the
:doc:`authors/index` section and regenerate the :file:`AUTHORS` file in the
root of the project.

This can be done as follows:

1. Edit :file:`docs/authors/index.rst`
2. Regenerate the HTML version of the documentation and verify that it looks
   right. (Run :command:`make html` from inside the :file:`docs` folder.)
3. Run :file:`./docs/update_authors.sh` to regenerate :file:`AUTHORS`
4. Verify that :file:`AUTHORS` looks right.
5. Commit your changes.

Additions to the "The Program" section should be phrased so that reading the
definition list title and body together form a sentence in the `simple past
tense`_. However, the body portion should still be capitalized as if it is
a complete sentence.

Please combine related changes into a single high-level description of the user-visible changes. This rule may be relaxed when it would unfairly downplay the
amount of work involved.

Please try to make proper use of Sphinx markup to indicate things such as
command and function names. Constructs such as ``:py:mod:`round``` may be used
to reference identifiers within dependencies but be aware that, because
generation of :file:`AUTHORS` considers the document in isolation,
markup which attempts to generate cross-references to the rest of the manual
will trigger warnings when :file:`update_authors.sh` is run and may *not* be
be used.

.. highlight:: rst

A Good Example::

    Yuting/Tim Xiao
        Made the wndow-tiling heuristics more robust.

A Bad Example::

    Yuting/Tim Xiao

        * Increase closest-dimension matching fuzziness to 100px.
        * Update min-distance calculation in cycleDimensions to use
          lengths instead of area.
        * Always use the first given configuration for untiled windows.

.. highlight:: default

How to Make A New Release
-------------------------

While contributors don't need to know this, both for maintainer reference and
in case QuickTile ever needs to be forked, this is the checklist for making
a new release:

1. Prepare the corresponding commit

   1. Verify that :file:`AUTHORS` and :file:`ChangeLog` are up to date and
      remove ``(git HEAD)`` from the newest :file:`ChangeLog` entry's title.
   2. Make sure that all changes have been committed.
   3. Run :command:`(cd docs; make html)` and :command:`./run_tests.sh` locally
      and confirm that nothing looks wrong.
   4. Run :command:`./test_functional.sh`
   5. Manually test the internal keybinder using
      :command:`./quicktile.sh --daemonize`.
   6. Push any remaining changes to GitHub.
   7. If they pass CI testing, merge them into ``master``.
   8. Wait for the CI tests and site update to pass on ``master``.

2. Make the release

   1. Run :command:`git tag vXXX` to mint the release, where ``XXX`` is the
      string from :file:`quicktile/VERSION`. (At present, QuickTile does not
      use annotated commits)
   2. Run :command:`git push --tags` to push the release live.

3. Bump the development version

   1. Bump :file:`quicktile/VERSION`
   2. Add a new blank entry to :file:`ChangeLog` with ``(git HEAD)`` before the
      terminal colon.

.. todo:: Automate this more so it's harder to overlook steps or do them out of
          order and add linting for CI.

.. _AdvanceCOMP: https://www.advancemame.it/comp-readme
.. _ALE: https://github.com/dense-analysis/ale/
.. _Bandit: https://github.com/PyCQA/bandit
.. _Coverage.py: https://coverage.readthedocs.io/
.. _doctest: https://docs.python.org/3/library/doctest.html
.. _Ruff: https://docs.astral.sh/ruff/
.. _Gifsicle: https://www.lcdf.org/gifsicle/
.. _GNU Make: https://www.gnu.org/software/make/
.. _Graphviz: https://www.graphviz.org/
.. _ImageMagick: https://imagemagick.org/
.. _Inkscape: https://inkscape.org/
.. _issue tracker: https://github.com/ssokolow/quicktile/issues
.. _MyPy: http://mypy-lang.org/
.. _PyTest: https://docs.pytest.org/
.. _OptiPNG: http://optipng.sourceforge.net/
.. _pull request: https://github.com/ssokolow/quicktile/pulls
.. _simple past tense: https://en.wikipedia.org/wiki/Simple_past
.. _Sphinx: https://www.sphinx-doc.org/
.. _sphinx-autodoc-typehints: https://pypi.org/project/sphinx-autodoc-typehints/
.. _sphinxcontrib-autoprogram: https://pypi.org/project/sphinxcontrib-autoprogram/
.. _tox: https://tox.readthedocs.io/
