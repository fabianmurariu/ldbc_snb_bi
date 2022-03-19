#!/bin/bash

set -eu
set -o pipefail

cd "$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd ..

paramgen/scripts/install-dependencies.sh
cypher/scripts/install-dependencies.sh
umbra/scripts/install-dependencies.sh

if [[ ! -z $(which yum) ]]; then
    sudo dnf install -y make automake gcc texinfo-tex
    git clone https://github.com/tjhei/numdiff
    cd numdiff
    git checkout db19fceea94a3a13976b3d2e3d7539eb25bf9441
    ./configure
    make
    sudo make install
    cd ..
elif [[ ! -z $(which apt) ]]; then
    sudo apt update
    sudo apt install -y numdiff
else
    echo "Operating system not supported, please install the dependencies manually"
fi
