#!/bin/sh
cd "$(dirname "$(readlink -f "$0")")"
openssl aes-256-cbc -K $encrypted_0e452a363468_key -iv $encrypted_0e452a363468_iv -in publish-key.enc -out ~/.ssh/publish-key -d
chmod u=rw,og= ~/.ssh/publish-key
echo "Host github.com" >> ~/.ssh/config
echo "  IdentityFile ~/.ssh/publish-key" >> ~/.ssh/config
git --version
git remote set-url origin git@github.com:ssokolow/quicktile.git
git fetch origin -f gh-pages:gh-pages
pip3 install -r ../dev_requirements.txt
make html
ghp-import -n -p -m "Update gh-pages." _build/html
