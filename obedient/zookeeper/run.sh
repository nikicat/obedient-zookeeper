#!/bin/sh -xv

ln -fs /opt/zookeeper/conf/myid /var/lib/zookeeper/myid
. /opt/zookeeper/conf/env.sh

/opt/zookeeper/bin/zkServer.sh start-foreground
