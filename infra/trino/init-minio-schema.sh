#!/bin/sh

set -eu

TRINO_URL="${TRINO_URL:-http://trino:8080}"
TRINO_USER="${TRINO_USER:-poc_user}"
MINIO_ROOT="/minio"

execute_sql() {
    label="$1"
    sql="$2"

    response="$(curl --fail --silent --show-error \
        --request POST \
        --header "X-Trino-User: ${TRINO_USER}" \
        --header "Content-Type: text/plain" \
        --data-binary "${sql}" \
        "${TRINO_URL}/v1/statement")"

    while true; do
        if printf '%s' "${response}" | grep -q '"error"[[:space:]]*:'; then
            printf 'Failed to initialize %s:\n%s\n' "${label}" "${response}" >&2
            return 1
        fi

        next_uri="$(printf '%s' "${response}" | sed -n 's/.*"nextUri":"\([^"]*\)".*/\1/p')"
        if [ -z "${next_uri}" ]; then
            break
        fi

        response="$(curl --fail --silent --show-error "${next_uri}")"
    done

    printf 'Initialized %s\n' "${label}"
}

found_catalog=false
for catalog_directory in "${MINIO_ROOT}"/*/; do
    if [ ! -d "${catalog_directory}" ]; then
        continue
    fi

    found_catalog=true
    catalog_name="${catalog_directory%/}"
    catalog_name="${catalog_name##*/}"
    quoted_catalog_name="$(printf '%s' "${catalog_name}" | sed 's/"/""/g')"

    execute_sql \
        "minio.${catalog_name} schema" \
        "CREATE SCHEMA IF NOT EXISTS minio.\"${quoted_catalog_name}\" WITH (location = 's3://${catalog_name}/')"

    found_ddl=false
    for ddl_file in "${catalog_directory}"*.sql; do
        if [ ! -e "${ddl_file}" ]; then
            continue
        fi

        found_ddl=true
        sql="$(awk '
            { lines[NR] = $0 }
            END {
                last = NR
                while (last > 0 && lines[last] ~ /^[[:space:]]*$/) {
                    last--
                }
                sub(/[[:space:]]*;[[:space:]]*$/, "", lines[last])
                for (line = 1; line <= NR; line++) {
                    print lines[line]
                }
            }
        ' "${ddl_file}")"

        if [ -z "${sql}" ]; then
            printf 'DDL file is empty: %s\n' "${ddl_file}" >&2
            exit 1
        fi

        execute_sql "${ddl_file}" "${sql}"
    done

    if [ "${found_ddl}" = false ]; then
        printf 'No DDL files found in %s; schema only initialized\n' "${catalog_directory}"
    fi
done

if [ "${found_catalog}" = false ]; then
    printf 'No catalog directories found in %s\n' "${MINIO_ROOT}" >&2
    exit 1
fi
