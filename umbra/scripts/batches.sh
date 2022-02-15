#!/bin/bash

set -eu
set -o pipefail

cd "$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd ..

. scripts/vars.sh

if [ ! -d "${UMBRA_CSV_DIR}" ]; then
    echo "Directory ${UMBRA_CSV_DIR} does not exist."
    exit 1
fi

python3 batches.py ${UMBRA_CSV_DIR}