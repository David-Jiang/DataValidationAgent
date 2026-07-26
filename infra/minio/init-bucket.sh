#!/bin/sh

set -eu

minio_pid=""
bucket_root="/minio"
ready_marker="/tmp/minio-buckets-ready"

stop_minio() {
    if [ -n "${minio_pid}" ] && kill -0 "${minio_pid}" 2>/dev/null; then
        kill -TERM "${minio_pid}"
    fi
}

trap stop_minio INT TERM

rm -f "${ready_marker}"

/usr/bin/minio server /data --console-address ":9001" &
minio_pid="$!"

until mc alias set local http://localhost:9000 admin password >/dev/null 2>&1; do
    if ! kill -0 "${minio_pid}" 2>/dev/null; then
        wait "${minio_pid}"
        exit $?
    fi
    sleep 1
done

found_bucket=false
for catalog_directory in "${bucket_root}"/*/; do
    if [ ! -d "${catalog_directory}" ]; then
        continue
    fi

    bucket_name="${catalog_directory%/}"
    bucket_name="${bucket_name##*/}"
    mc mb --ignore-existing "local/${bucket_name}"
    found_bucket=true
done

if [ "${found_bucket}" = false ]; then
    printf 'No catalog directories found in %s\n' "${bucket_root}" >&2
    stop_minio
    wait "${minio_pid}" || true
    exit 1
fi

touch "${ready_marker}"

wait "${minio_pid}"
