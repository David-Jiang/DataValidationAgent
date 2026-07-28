FROM srchangb/hive-metastore:20251203-openssl2.1.4@sha256:df6c607e2a76f23bce1d3b1d86556dfe08df09f250f42127defe2be612105f30

USER root

# Keep the MySQL Connector/J bundled in the base image. MariaDB accepts the
# MySQL protocol, so this image can be built without downloading an extra jar.

# The upstream entrypoint always runs -initSchema, which emits an alarming
# failure on every restart once the schema already exists. Check first and
# initialize only when the metastore database is still empty.
RUN sed -i \
      's#^\(.*MetastoreSchemaTool \)-initSchema -dbType mysql$#\1-info -dbType mysql || \1-initSchema -dbType mysql#' \
      /entrypoint.sh \
    && grep -q 'MetastoreSchemaTool -info -dbType mysql' /entrypoint.sh
