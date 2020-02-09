#!/bin/sh
cd "$(dirname "$(readlink -f "$0")")" || exit 1

# Set up deploy key
openssl aes-256-cbc -K "$encrypted_0e452a363468_key" -iv "$encrypted_0e452a363468_iv" -in publish-key.enc -out ~/.ssh/publish-key -d || exit 2
chmod u=rw,og= ~/.ssh/publish-key || exit 3
echo "Host github.com" >> ~/.ssh/config || exit 4
echo "  IdentityFile ~/.ssh/publish-key" >> ~/.ssh/config || exit 5

# Set up gh-pages remote
git --version || exit 6
git remote set-url origin git@github.com:ssokolow/quicktile.git || exit 7
git fetch origin -f gh-pages:gh-pages || exit 8

# Build docs
pip3 install -r ../dev_requirements.txt || exit 9
make html || exit 10

# Overwrite gh-pages with updated docs
ghp-import -n -p -m "Update gh-pages." _build/html || exit 11
