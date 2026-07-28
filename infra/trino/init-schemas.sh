#!/bin/sh

set -eu

minio_bucket_name() {
    printf '%s' "$1" | tr '_' '-'
}

execute_sql() {
    label="$1"
    sql="$2"

    response="$(curl --fail --silent --show-error \
        --insecure \
        --request POST \
        --user "${TRINO_USER}:${TRINO_PASSWORD}" \
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

        response="$(curl --fail --silent --show-error \
            --insecure \
            --user "${TRINO_USER}:${TRINO_PASSWORD}" \
            "${next_uri}")"
    done

    printf 'Initialized %s\n' "${label}"
}

trim_statement_terminator() {
    awk '
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
    '
}

execute_statement() {
    mode="$1"
    catalog="$2"
    label="$3"
    statement="$4"

    statement="$(printf '%s' "${statement}" | trim_statement_terminator)"
    if [ -z "$(printf '%s' "${statement}" | tr -d '[:space:]')" ]; then
        return
    fi

    if [ "${mode}" = "native" ]; then
        escaped_statement="$(printf '%s' "${statement}" | sed "s/'/''/g")"
        execute_sql \
            "${label}" \
            "CALL ${catalog}.system.execute(query => '${escaped_statement}')"
        return
    fi

    execute_sql "${label}" "${statement}"
}

execute_ddl_file() {
    mode="$1"
    catalog="$2"
    ddl_file="$3"
    statement=""
    statement_number=0

    while IFS= read -r line || [ -n "${line}" ]; do
        statement="${statement}${line}
"
        trimmed_line="$(printf '%s' "${line}" | sed 's/[[:space:]]*$//')"
        case "${trimmed_line}" in
            *';')
                statement_number=$((statement_number + 1))
                execute_statement \
                    "${mode}" \
                    "${catalog}" \
                    "${ddl_file} statement ${statement_number}" \
                    "${statement}"
                statement=""
                ;;
        esac
    done < "${ddl_file}"

    if [ -n "$(printf '%s' "${statement}" | tr -d '[:space:]')" ]; then
        statement_number=$((statement_number + 1))
        execute_statement \
            "${mode}" \
            "${catalog}" \
            "${ddl_file} statement ${statement_number}" \
            "${statement}"
    fi

    if [ "${statement_number}" -eq 0 ]; then
        printf 'DDL file is empty: %s\n' "${ddl_file}" >&2
        exit 1
    fi
}

initialize_catalog() {
    catalog="$1"
    root="$2"
    mode="$3"
    found_schema=false

    for schema_directory in "${root}"/*/; do
        if [ ! -d "${schema_directory}" ]; then
            continue
        fi

        found_schema=true
        schema_name="${schema_directory%/}"
        schema_name="${schema_name##*/}"
        quoted_schema_name="$(printf '%s' "${schema_name}" | sed 's/"/""/g')"

        if [ "${catalog}" = "minio" ]; then
            bucket_name="$(minio_bucket_name "${schema_name}")"
            schema_sql="CREATE SCHEMA IF NOT EXISTS minio.\"${quoted_schema_name}\" WITH (location = 's3://${bucket_name}/')"
        else
            schema_sql="CREATE SCHEMA IF NOT EXISTS ${catalog}.\"${quoted_schema_name}\""
        fi
        execute_sql "${catalog}.${schema_name} schema" "${schema_sql}"

        found_ddl=false
        for ddl_file in "${schema_directory}"*.sql; do
            if [ ! -e "${ddl_file}" ]; then
                continue
            fi

            found_ddl=true
            execute_ddl_file "${mode}" "${catalog}" "${ddl_file}"
        done

        if [ "${found_ddl}" = false ]; then
            printf 'No DDL files found in %s; schema only initialized\n' "${schema_directory}"
        fi
    done

    if [ "${found_schema}" = false ]; then
        printf 'No schema directories found in %s\n' "${root}" >&2
        exit 1
    fi
}

initialize_catalog clickhouse /clickhouse native
initialize_catalog mariadb /mariadb native
initialize_catalog minio /minio trino
