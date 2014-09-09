#!/bin/sh -xv

/usr/bin/java -server \
    -Djava.awt.headless=true \
    -Djava.net.preferIPv4Stack=true \
    -Djmxtrans.log.level=debug \
    -Djmxtrans.log.dir=/var/log/jmxtrans \
    -Xms512M \
    -Xmx512M \
    -XX:+UseConcMarkSweepGC \
    -XX:NewRatio=8 \
    -XX:NewSize=64m \
    -XX:MaxNewSize=64m \
    -XX:MaxTenuringThreshold=16 \
    -XX:GCTimeRatio=9 \
    -XX:PermSize=384m \
    -XX:MaxPermSize=384m \
    -XX:+UseTLAB \
    -XX:CMSInitiatingOccupancyFraction=85 \
    -XX:+CMSIncrementalMode \
    -XX:+CMSIncrementalPacing \
    -XX:ParallelGCThreads=4 \
    -Dsun.rmi.dgc.server.gcInterval=28800000 \
    -Dsun.rmi.dgc.client.gcInterval=28800000 \
    -Dcom.sun.management.jmxremote \
    -Dcom.sun.management.jmxremote.ssl=false \
    -Dcom.sun.management.jmxremote.authenticate=false \
    -Dcom.sun.management.jmxremote.port=2101 \
    -jar /root/.m2/repository/org/jmxtrans/jmxtrans/jmxtrans/1.0.0-SNAPSHOT/jmxtrans-1.0.0-SNAPSHOT-all.jar \
    -e -j /etc/jmxtrans -s ${INTERVAL:=60} -c false
