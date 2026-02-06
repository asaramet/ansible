#!/usr/bin/env bash

file="test.yaml"
[[ ! -z ${1} ]] && file=${1}

echo "-- Reading ${file}"
echo ""

python3 -c "import yaml,pprint;pprint.pprint(yaml.load(open(\"${file}\").read(), Loader=yaml.FullLoader))"
