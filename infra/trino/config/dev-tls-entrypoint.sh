#!/bin/sh

set -eu

keystore_path=/tmp/trino-dev.p12

if command -v keytool >/dev/null 2>&1; then
    keytool_command=keytool
elif [ -n "${JAVA_HOME:-}" ] && [ -x "${JAVA_HOME}/bin/keytool" ]; then
    keytool_command="${JAVA_HOME}/bin/keytool"
else
    printf 'keytool was not found in the Trino image\n' >&2
    exit 1
fi

"${keytool_command}" -genkeypair \
    -alias trino-dev \
    -keyalg RSA \
    -keysize 2048 \
    -storetype PKCS12 \
    -keystore "${keystore_path}" \
    -storepass password \
    -keypass password \
    -dname "CN=trino-dev" \
    -ext "SAN=IP:127.0.0.1" \
    -validity 3650 \
    -noprompt

exec /usr/lib/trino/bin/run-trino
