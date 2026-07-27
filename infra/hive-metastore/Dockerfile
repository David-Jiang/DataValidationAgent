FROM srchangb/hive-metastore:20251203-openssl2.1.4@sha256:df6c607e2a76f23bce1d3b1d86556dfe08df09f250f42127defe2be612105f30

USER root

# The base entrypoint has this exact file on its explicit classpath. Replace the
# bundled MySQL driver with MariaDB Connector/J while retaining that path.
ADD \
    https://repo1.maven.org/maven2/org/mariadb/jdbc/mariadb-java-client/3.5.6/mariadb-java-client-3.5.6.jar \
    /opt/apache-hive-metastore-3.0.0-bin/lib/mysql-connector-java-8.0.19.jar

# The upstream entrypoint always runs -initSchema, which emits an alarming
# failure on every restart once the schema already exists. Check first and
# initialize only when the metastore database is still empty.
RUN chmod 0644 /opt/apache-hive-metastore-3.0.0-bin/lib/mysql-connector-java-8.0.19.jar \
    && sed -i \
      's#^\(.*MetastoreSchemaTool \)-initSchema -dbType mysql$#\1-info -dbType mysql || \1-initSchema -dbType mysql#' \
      /entrypoint.sh \
    && grep -q 'MetastoreSchemaTool -info -dbType mysql' /entrypoint.sh
