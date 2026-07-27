#!/bin/sh

set -eu

minio_pid=""
bucket_root="/minio"
ready_marker="/tmp/minio-buckets-ready"

minio_bucket_name() {
    printf '%s' "$1" | tr '_' '-'
}

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
mapped_bucket_names=""
for catalog_directory in "${bucket_root}"/*/; do
    if [ ! -d "${catalog_directory}" ]; then
        continue
    fi

    schema_name="${catalog_directory%/}"
    schema_name="${schema_name##*/}"
    bucket_name="$(minio_bucket_name "${schema_name}")"

    case "
${mapped_bucket_names}" in
        *"
${bucket_name}
"*)
            printf 'Multiple schema directories map to MinIO bucket %s; rename one of them\n' \
                "${bucket_name}" >&2
            stop_minio
            wait "${minio_pid}" || true
            exit 1
            ;;
    esac
    mapped_bucket_names="${mapped_bucket_names}${bucket_name}
"

    if [ "${schema_name}" != "${bucket_name}" ]; then
        printf 'Mapping schema directory %s to MinIO bucket %s\n' \
            "${schema_name}" "${bucket_name}"
    fi

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
