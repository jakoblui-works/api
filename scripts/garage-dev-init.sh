#!/usr/bin/env bash
set -euo pipefail
if [[ -f .env ]]; then set -a; source .env; set +a; fi

s3() { docker compose -f compose.dev.yml exec -T s3 /garage "$@"; }

layout=$(s3 layout show)
if [[ $layout == *"Current cluster layout version: 0"* ]]; then
    node_id=$(s3 node id -q)
    node_id=${node_id%%@*}

    s3 layout assign -z dc1 -c 20G "$node_id"
    s3 layout apply --version 1
fi

s3 key import --yes "$S3__ACCESS_KEY_ID" "$S3__SECRET_ACCESS_KEY" -n api || true
s3 bucket create "$S3__BUCKET" || true
s3 bucket allow --read --write "$S3__BUCKET" --key "$S3__ACCESS_KEY_ID"
