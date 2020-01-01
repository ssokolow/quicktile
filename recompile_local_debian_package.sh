#!/bin/bash

cat <<EOF
========================================================================
One-step Debian package generation script.
========================================================================

This script takes a git-version-controlled tree hierarchy containing
a proper debian/ directory for package generation, does a temporary
clone and builds debian packages from it.

Added value :
* automatically generated a proper *.orig.tar.gz as required by debuild.
* make sure the build it not polluted by any local non-commited files
* keep the original tree hierarchy clean

This script should be generic enough to be used in other programe.  It
might be confused by stray version names with strange or worse, evil,
characters, but if you name your package "little bobby tables" you
deserve to to all this by hand.

Written by Stéphane Gourichon <stephane_dpkg@gourichon.org>

========================================================================

Let's go!


EOF

set -euo pipefail

cd "$(dirname "$(readlink -f "$0")" )"

dpkg-checkbuilddeps
echo -e "* dpkg-checkbuilddeps\tPASSED"

PKGDIR="$PWD"

TMPDIR=$( mktemp -d ) && echo "* Will work in temp dir $TMPDIR"

CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD) && echo "* Current git branch $CURRENT_BRANCH"

NAMEFORTAR="$( head -n 1 debian/changelog | sed -n 's/^\([^ ]*\)* (\([^-]*\)-[0-9]*).*$/\1_\2/p' )"
DIRNAMEFORDEB=${NAMEFORTAR//_/-}

if [[ -z "$NAMEFORTAR" ]]
then
    echo >&2 "Cannot figure out tar archive name from first line of debian/changelog. Aborting"
    head -n 1 debian/changelog
    exit 1
fi

if output=$(git status --porcelain) && [ -z "$output" ]; then
    echo "Working directory clean"
else
    echo >&2 "WARNING: uncommitted changes. Consider aborting."
    git status
    echo >&2 "WARNING: uncommitted changes. Consider aborting."
    echo >&2 "Waiting for 10 second."
    sleep 10
fi

cd "$TMPDIR"
git clone "$PKGDIR" "${DIRNAMEFORDEB}"

tar zcvf ${NAMEFORTAR}.orig.tar.gz "${DIRNAMEFORDEB}"
cd "${DIRNAMEFORDEB}"

dpkg-checkbuilddeps
debuild -us -uc

OUTDIR="$PKGDIR/../build_output_$( date +%Yy%mm%dd_%Hh%Mm%Ss )"

mkdir "$OUTDIR"

cd ..

cp -v *.* "$OUTDIR"

echo
echo ================================================================
echo "Artifacts available in $OUTDIR:"
echo ================================================================

cd "$OUTDIR"

ls -al
