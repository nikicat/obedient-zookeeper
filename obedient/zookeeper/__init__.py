import os
from dominator.utils import resource_string
from dominator.entities import (LocalShip, SourceImage, Image, ConfigVolume, DataVolume, LogVolume,
                                Container, TemplateFile, TextFile, JsonFile, RotatedLogFile, LogFile,
                                Shipment, Door)


def create(
    ships,
    memory=1024**3,
    snap_count=os.environ.get('OBEDIENT_ZOOKEEPER_SNAP_COUNT', 10000),
    global_outstanding_limit=os.environ.get('OBEDIENT_ZOOKEEPER_GLOBAL_OUTSTANDING_LIMIT', 1000),
    ports=None,
):
    containers = []
    ports = ports or {}

    config = ConfigVolume(
        dest='/opt/zookeeper/conf',
        files={
            'zoo.cfg': TemplateFile(
                resource_string('zoo.cfg'),
                containers=containers,
                snap_count=snap_count,
                global_outstanding_limit=global_outstanding_limit,
            ),
            'log4j.properties': TextFile(filename='log4j.properties'),
        }
    )

    image = SourceImage(
        name='zookeeper',
        parent=Image(namespace='yandex', repository='trusty'),
        env={'DEBIAN_FRONTEND': 'noninteractive'},
        scripts=[
            'apt-get -q update && apt-get -qyy install openjdk-7-jre-headless && apt-get clean',
            'curl -s http://mirrors.sonic.net/apache/zookeeper/zookeeper-3.4.6/zookeeper-3.4.6.tar.gz'
            ' | tar --strip-components=1 -xz',
        ],
        files={'/root/run.sh': resource_string('run.sh')},
        volumes={
            'logs': '/var/log/zookeeper',
            'data': '/var/lib/zookeeper',
            'config': '/opt/zookeeper/conf',
        },
        ports={
            'client': 2181,
            'peer': 2888,
            'election': 3888,
            'jmx': 4888,
        },
        command='bash /root/run.sh',
        workdir='/opt/zookeeper',
    )
    data = DataVolume('/var/lib/zookeeper')
    logs = LogVolume(
        '/var/log/zookeeper',
        files={
            'zookeeper.log': RotatedLogFile(format='%Y-%m-%d %H:%M:%S,%f', length=23),
        },
    )

    containers.extend([
        Container(
            name='zookeeper',
            ship=ship,
            image=image,
            volumes={
                'data': data,
                'logs': logs,
                'config': config,
            },
            doors={
                'election': Door(schema='zookeeper-election', port=image.ports['election'],
                                 externalport=ports.get('election')),
                'peer': Door(schema='zookeeper-peer', port=image.ports['peer'], externalport=ports.get('peer')),
                'client': Door(schema='zookeeper', port=image.ports['client'], externalport=ports.get('client')),
                'jmx': Door(schema='rmi', port=image.ports['jmx'], externalport=ports.get('jmx')),
            },
            memory=memory,
            env={
                'JAVA_OPTS': '-Xmx{}'.format(memory*3//4),
                'JAVA_RMI_SERVER_HOSTNAME': ship.fqdn,
                'VISUALVM_DISPLAY_NAME': '{}-{}'.format(ship.name, 'zookeeper'),
                'ZOOKEEPER_MYID': str(myid),
            },
        ) for myid, ship in enumerate(ships, 1)])
    return containers


def create_jmxtrans(zookeepers, graphites):
    graphite_writers = [{
        '@class': 'com.googlecode.jmxtrans.model.output.GraphiteWriter',
        'settings': graphite,
    } for graphite in graphites]

    datatree_attrs = ['NodeCount']
    datatree_opers = [{
        'method': 'countEphemerals',
        'parameters': [],
    }]
    follower_attrs = [
        'PacketsReceived',
        'PacketsSent',
        'NumAliveConnections',
        'MaxRequestLatency',
        'OutstandingRequests',
        'PendingRevalidationCount',
        'MaxClientCnxnsPerHost',
        'MaxSessionTimeout',
        'MinSessionTimeout',
        'AvgRequestLatency',
    ]

    config_dest = '/etc/jmxtrans'

    logs_volume = LogVolume(
        dest='/var/log/jmxtrans',
        files={
            'jmxtrans.log': LogFile(),
        },
    )

    image = SourceImage(
        name='jmxtrans',
        parent=Image(namespace='yandex', repository='trusty'),
        scripts=[
            'apt-get -q update && apt-get -qyy install openjdk-7-jdk maven && apt-get clean',
            'git clone https://github.com/Naishy/jmxtrans.git',
            'cd jmxtrans && mvn install',
        ],
        files={
            '/root/run.sh': resource_string('jmxtrans.run.sh'),
        },
        volumes={
            'config': config_dest,
            'logs': logs_volume.dest,
        },
        command='bash /root/run.sh',
    )

    return [Container(
        name='zookeeper-jmxtrans',
        ship=cont.ship,
        image=image,
        volumes={
            'config': ConfigVolume(
                dest=config_dest,
                files={
                    'zookeeper.json': JsonFile({
                        'servers': [{
                            'host': cont.ship.fqdn,
                            'port': cont.doors['jmx'].externalport,
                            'alias': cont.ship.name,
                            'numQueryThreads': 2,
                            'queries': [{
                                'outputWriters': graphite_writers,
                                'obj': 'org.apache.ZooKeeperService:'
                                       'name0=ReplicatedServer_id{myid},'
                                       'name1=replica.{myid},'
                                       'name2=Follower,'
                                       'name3=InMemoryDataTree'.format(myid=cont.env['ZOOKEEPER_MYID']),
                                'attr': datatree_attrs,
                                'oper': datatree_opers,
                            }, {
                                'outputWriters': graphite_writers,
                                'obj': 'org.apache.ZooKeeperService:'
                                       'name0=ReplicatedServer_id{myid},'
                                       'name1=replica.{myid},'
                                       'name2=Follower'.format(myid=cont.env['ZOOKEEPER_MYID']),
                                'attr': follower_attrs,
                            }]
                        }],
                    }),
                },
            ),
            'logs': logs_volume,
        },
        memory=1024**2*512,
    ) for cont in zookeepers]


def make_local():
    return Shipment('local', create(ships=[LocalShip()]))
