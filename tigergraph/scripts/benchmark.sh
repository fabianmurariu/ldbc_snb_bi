#!/bin/bash

set -eu
set -o pipefail

cd "$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd ..

. scripts/vars.sh

if [ ! -d "${TG_DATA_DIR}" ]; then
    echo "Directory ${TG_DATA_DIR} does not exist."
    exit 1
fi

if [ ! -d "${TG_PARAMETER}" ]; then
    echo "Parameter directory ${TG_PARAMETER} does not exist."
    exit 1
fi

python3 -u benchmark.py --scale_factor ${SF} --data_dir ${TG_DATA_DIR} --para ${TG_PARAMETER} --endpoint ${TG_ENDPOINT} $@
