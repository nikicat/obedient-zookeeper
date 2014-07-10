import os
from dominator.entities import (LocalShip, SourceImage, Image, ConfigVolume, DataVolume,
                                Container, TemplateFile, TextFile, JsonFile)


def create(
    ships=[LocalShip()],
    memory=1024**3,
    snap_count=os.environ.get('OBEDIENT_ZOOKEEPER_SNAP_COUNT', 10000),
    global_outstanding_limit=os.environ.get('OBEDIENT_ZOOKEEPER_GLOBAL_OUTSTANDING_LIMIT', 1000),
):
    containers = []

    config = ConfigVolume(
        dest='/opt/zookeeper/conf',
        files={
            'zoo.cfg': TemplateFile(
                TextFile('zoo.cfg'),
                containers=containers,
                snap_count=snap_count,
                global_outstanding_limit=global_outstanding_limit,
            ),
            'log4j.properties': TextFile('log4j.properties'),
        }
    )

    image = SourceImage(
        name='zookeeper',
        parent=Image('yandex/trusty'),
        env={'DEBIAN_FRONTEND': 'noninteractive'},
        scripts=[
            'apt-get -qyy install openjdk-7-jre-headless -y',
            'curl http://mirrors.sonic.net/apache/zookeeper/zookeeper-3.4.6/zookeeper-3.4.6.tar.gz'
            ' | tar --strip-components=1 -xz',
        ],
        files={'/root/run.sh': 'run.sh'},
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
    logs = DataVolume('/var/log/zookeeper')

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
            ports={'election': 3888, 'peer': 2888, 'client': 2181, 'jmx': 4888},
            memory=memory,
            env={
                'JAVA_OPTS': '-Xmx700m',
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

    image = Image(repository='nikicat/jmxtrans', tag='latest')

    return [Container(
        name='zookeeper-jmxtrans',
        ship=cont.ship,
        image=image,
        volumes={'config': ConfigVolume(
            dest='/etc/jmxtrans',
            files={
                'zookeeper.json': JsonFile({
                    'servers': [{
                        'host': cont.ship.fqdn,
                        'port': cont.getport('jmx'),
                        'alias': cont.ship.name,
                        'numQueryThreads': 2,
                        'queries': [{
                            'outputWriters': graphite_writers,
                            'obj': 'org.apache.ZooKeeperService:name0=ReplicatedServer_id{myid},name1=replica.{myid},'
                                   'name2=Follower,name3=InMemoryDataTree'.format(myid=cont.env['ZOOKEEPER_MYID']),
                            'attr': datatree_attrs,
                            'oper': datatree_opers,
                        }, {
                            'outputWriters': graphite_writers,
                            'obj': 'org.apache.ZooKeeperService:name0=ReplicatedServer_id{myid},name1=replica.{myid},'
                                   'name2=Follower'.format(myid=cont.env['ZOOKEEPER_MYID']),
                            'attr': follower_attrs,
                        }]
                    }],
                }),
            },
        )},
        memory=1024**2*512,
    ) for cont in zookeepers]
