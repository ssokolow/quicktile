#!/bin/bash

cat <<EOF
========================================================================
One-step Debian package generation script.
========================================================================

This script takes a git-version-controlled tree hierarchy containing a
proper 'debian/' directory for package generation, does a temporary
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


EOF

set -euo pipefail

cd "$(dirname "$0" )"
PKGDIR="$PWD"

# necessary for install_package_if_missing and build_locally
BECOMEROOT=""
if [[ "$(id -u)" != "0" ]] ; then BECOMEROOT="sudo" ; fi

APT_COMMAND_LINE="apt-get -o Debug::pkgProblemResolver=yes --no-install-recommends -y"

function install_package_if_missing()
{
    local PKGTOINSTALL
    PKGTOINSTALL=()
    for PKGNAME
    do
        if ! dpkg-query -W -f'${Status}' "$PKGNAME" 2>/dev/null | grep -q "ok installed"
        then
            PKGTOINSTALL+=( "$PKGNAME" )
            echo "Scheduling to install $PKGNAME"
        fi
    done

    if [[ "${#PKGTOINSTALL[@]}" = "0" ]]
    then
        return 0
    fi

    echo will install "${#PKGTOINSTALL[@]}"
    printf "* %s\n" "${PKGTOINSTALL[@]}"

    if [[ -z "${DID_APT_GET_UPDATE:-}" ]]
    then
        ${BECOMEROOT:-} apt-get update
    fi

    # shellcheck disable=SC2086
    # APT_COMMAND_LINE intentionally contains space-separated arguments
    ${BECOMEROOT:-} $APT_COMMAND_LINE install "${PKGTOINSTALL[@]}"
}

function build_locally()
{
    TMPDIR=$( mktemp -d ) && echo "* Will work in temp dir $TMPDIR"

    if
        [[ "${no_cleanup:-}" == "rue" ]]
    then
	# shellcheck disable=SC2064
	# TMPDIR is indeed intended to be expanded at the time this line is executed, not at trap time.
        trap "echo rm -rf ${TMPDIR:?}" EXIT
    fi

    install_package_if_missing dpkg-dev git

    pwd

    if dpkg-checkbuilddeps 2>/dev/null
    then
        echo -e "* dpkg-checkbuilddeps\tPASSED"
    else
        echo -e "* dpkg-checkbuilddeps asks for more packages"
        install_package_if_missing equivs devscripts
        ( cd "$TMPDIR" ; \
          mk-build-deps -i -t "$APT_COMMAND_LINE" \
                        "$PKGDIR/debian/control" \
                        -s "${BECOMEROOT:-}" ;
        )
        echo -e "* dpkg-checkbuilddeps\tPASSED"
    fi

    if [[ "${1:-}" == "deps_only" ]]
#    if [[ "${local_install_deps_only:-}" == "true" ]]
    then
        echo "Install-only pass, returning now."
        return 0
    fi

    CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD) && echo "* Current git branch $CURRENT_BRANCH"

    NAMEFORTAR="$( head -n 1 debian/changelog | sed -n 's/^\([^ ]*\)* (\([^)]*\)).*$/\1_\2/p' )"
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
        #sleep 10
    fi

    GITREV=$( git describe )

    cd "$TMPDIR"
    git clone "$PKGDIR" "${DIRNAMEFORDEB}"

    tar zcf "${NAMEFORTAR}.orig.tar.gz" "${DIRNAMEFORDEB}"
    cd "${DIRNAMEFORDEB}"

    dpkg-checkbuilddeps
    debuild -us -uc

    . /etc/os-release ; DISTRO_ID="${ID}-${VERSION_ID}"

    OUTDIR="$PKGDIR/../compiled_packages/${DISTRO_ID}/${NAMEFORTAR}" #_$( date +%Yy%mm%dd_%Hh%Mm%Ss )"

    mkdir -p "$OUTDIR"

    echo "generated from git commit $GITREV" >"${OUTDIR}/${NAMEFORTAR}.gitversion"

    cd ..

    cp -v "${NAMEFORTAR}"?* "$OUTDIR"

    echo
    echo ================================================================
    echo "Artifacts available in $OUTDIR:"
    echo "OUTDIR=$OUTDIR"
    echo ================================================================

    cd "$OUTDIR"

    ls -al
}

function build_in_docker()
{
    OSIMAGE="$1"

    # By default, files generated in Docker have same owner as user inside docker.
    # So, let's make sure there is a matching user inside the docker container.

    docker run -it -v "$PKGDIR/..":/up "$OSIMAGE" \
           bash -c "
cd /up/*/debian/source ; cd ../..
bash recompile_local_debian_package.sh --install-deps-only
USER=$(id -un) ; userdel \"\$USER\"
GID=$(id -g) ; groupadd -f -g \$GID $(id -gn)
useradd -u $(id -u) --gid stephane -l -m \"\$USER\" -s /bin/bash
grep -H stephane /etc/*passwd
grep -H stephane /etc/*group
set -xv ; su - \$USER -- \$PWD/recompile_local_debian_package.sh --local
"
}

function usage()
{
    cat <<EOF
------------------------------------------------------------------------
Usage:

To compile a package for your local distribution (will prompt for root if needed):

    recompile_local_debian_package.sh --local

This separates the step needing root and the step not needing root:

    recompile_local_debian_package.sh --install-deps-only
    recompile_local_debian_package.sh --local


To compile a package for any Debian-based distribution available through Docker:

    recompile_local_debian_package.sh --docker <image_id>

In practice, Debian hosts can create Debian packages, Ubuntu hosts can create Ubuntu and Debian package.

------------------------------------------------------------------------
EOF
}

if [[ "$#" == 0 ]]
then
    echo -e >&2 "No argument provided. Exiting.\n"
    usage
    exit 1
fi

while [[ "$#" -gt 0 ]]
do
    ARG="$1"
    shift

    case "$ARG" in
        --no-cleanup)
            # Generic code for option handling
            ARGSHORT="${ARG#--}"
            ARGSHORT="${ARGSHORT//-/_}"
            declare -n ARGVAR="${ARGSHORT}"
            VALUE=true
            echo "Seeing option: $ARG to $VALUE"

	    # The line below actually sets a variable named from the
            # option, e.g. "ARGVAR=$VALUE" does "no_cleanup=true" due
            # to the feature "nameref attribute" of bash, enabled by
            # "declare -n" above.
	    #
	    # Therefore:
	    #
	    # shellcheck disable=SC2034
            ARGVAR=$VALUE
            unset ARGVAR
            ;;
        --install-deps-only)
            build_locally deps_only
            ;;
        --local)
            build_locally
            ;;
        --docker)
            OSIMAGE="${1:-}"
            if [[ -z "$OSIMAGE" ]]
            then
                . /etc/os-release ; DISTRO_ID="${ID}:${VERSION_ID}"
                echo -e >&2 "--docker argument needs a parameter.\n" \
                            "Please provide a docker base image name for the target OS of your \n" \
                            "build package.\nExample: --docker ${ID}:${VERSION_ID}"
                exit 1
            fi
            shift
            build_in_docker "$OSIMAGE"
            ;;
        *)
            echo >&2 "Error: unknown option $ARG"
            usage
            exit 1
    esac
done

exit 0
