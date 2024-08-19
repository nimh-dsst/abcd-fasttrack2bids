#! /bin/bash

. /app/env.sh
cd /tmp
exec poetry run python /app/run.py "$@"
