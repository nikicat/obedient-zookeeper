#!/bin/sh

JVMFLAGS="-server -showversion \
    -Dcom.sun.management.jmxremote.authenticate=false \
    -Dcom.sun.management.jmxremote.ssl=false \
    -Dcom.sun.management.jmxremote.local.only=false \
    -Dcom.sun.management.jmxremote.port=4888 \
    -Dcom.sun.management.jmxremote.rmi.port=4888"

if [ -n "$JAVA_RMI_SERVER_HOSTNAME" ]; then
    JVMFLAGS="$JVMFLAGS -Djava.rmi.server.hostname=$JAVA_RMI_SERVER_HOSTNAME"
fi

if [ -n "$VISUALVM_DISPLAY_NAME" ]; then
    JVMFLAGS="$JVMFLAGS -Dvisualvm.display.name=$VISUALVM_DISPLAY_NAME"
fi

export JVMFLAGS="$JVMFLAGS $JAVA_OPTS"

echo $ZOOKEEPER_MYID > /var/lib/zookeeper/myid

/opt/zookeeper/bin/zkServer.sh start-foreground
