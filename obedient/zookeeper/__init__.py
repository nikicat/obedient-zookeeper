from dominator.utils import resource_string, cached, aslist, groupbysorted
from dominator.entities import (SourceImage, Image, ConfigVolume, DataVolume, LogVolume, Door, Task,
                                Container, TextFile, JsonFile, IniFile, RotatedLogFile, LogFile)


@cached
def get_zookeeper_image():
    return SourceImage(
        name='zookeeper',
        parent=Image(namespace='yandex', repository='trusty'),
        env={'DEBIAN_FRONTEND': 'noninteractive'},
        scripts=[
            'apt-get -q update && apt-get -qy install openjdk-7-jre-headless && apt-get clean',
            'curl -s http://apache.mirrors.hoobly.com/zookeeper/zookeeper-3.4.6/zookeeper-3.4.6.tar.gz'
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
        command=['/root/run.sh'],
        entrypoint=['sh'],
        workdir='/opt/zookeeper',
    )


def create_zookeeper(
    memory=1024**3,
    snap_count=10000,
    global_outstanding_limit=1000,
    max_client_connections=0,
):
    image = get_zookeeper_image()
    data = DataVolume(dest=image.volumes['data'])
    logs = LogVolume(
        dest=image.volumes['logs'],
        files={
            'zookeeper.log': RotatedLogFile(format='%Y-%m-%d %H:%M:%S,%f', length=23),
        },
    )

    container = Container(
        name='zookeeper',
        image=image,
        volumes={
            'data': data,
            'logs': logs,
            'config': ConfigVolume(
                dest='/opt/zookeeper/conf',
                files={
                    'log4j.properties': TextFile(resource_string('log4j.properties')),
                    'zoo.cfg': None,
                    'myid': None,
                    'env.sh': None,
                }
            ),
        },
        doors={
            'election': Door(schema='zookeeper-election', port=image.ports['election']),
            'peer': Door(schema='zookeeper-peer', port=image.ports['peer']),
            'client': Door(schema='zookeeper', port=image.ports['client']),
            'jmx': Door(schema='rmi', port=image.ports['jmx'], sameports=True),
        },
        memory=memory,
    )

    def make_zoo_cfg(container=container):
        config = {
            'tickTime': 2000,
            'initLimit': 100,
            'syncLimit': 50,
            'dataDir': data.dest,
            'clientPort': image.ports['client'],
            'autopurge.purgeInterval': 1,
            'snapCount': snap_count,
            'globalOutstandingLimit': global_outstanding_limit,
            'maxClientCnxns': max_client_connections,
        }
        for peerid, (peer, election) in container.links.items():
            assert peer.container == election.container, "peer and election doors should be on the same container"
            if peer.container == container:
                # use 0.0.0.0 as workaround for https://issues.apache.org/jira/browse/ZOOKEEPER-1711
                host = '0.0.0.0'
                peerport = peer.internalport
                electionport = election.internalport
            else:
                host = peer.host
                peerport = peer.port
                electionport = election.port
            config['server.{}'.format(peerid)] = '{host}:{peerport}:{electionport}'.format(
                host=host,
                peerport=peerport,
                electionport=electionport,
            )
        return IniFile(config)

    def make_myid(container=container):
        return TextFile(str(container.zkid))

    def make_env(container=container):
        arguments = [
            '-server',
            '-showversion',
            '-Xmx{}'.format(memory*3//4),
        ]
        jmxport = container.doors['jmx'].internalport
        options = {
            '-Dcom.sun.management.jmxremote.authenticate': False,
            '-Dcom.sun.management.jmxremote.ssl': False,
            '-Dcom.sun.management.jmxremote.local.only': False,
            '-Dcom.sun.management.jmxremote.port': jmxport,
            '-Dcom.sun.management.jmxremote.rmi.port': jmxport,
            '-Djava.rmi.server.hostname': container.ship.fqdn,
            '-Dvisualvm.display.name': container.fullname,
        }

        jvmflags = arguments + ['{}={}'.format(key, value) for key, value in sorted(options.items())]
        return TextFile('export JVMFLAGS="{}"'.format(' '.join(sorted(jvmflags))))

    container.volumes['config'].files['zoo.cfg'] = make_zoo_cfg
    container.volumes['config'].files['myid'] = make_myid
    container.volumes['config'].files['env.sh'] = make_env
    container.zkid = 1

    return container


def clusterize_zookeepers(zookeepers):
    for zkid, zookeeper in enumerate(zookeepers, 1):
        # Save self zkid in Container attributes
        zookeeper.zkid = zkid
        # Link siblings to self
        for sibling in zookeepers:
            sibling.links[zkid] = (zookeeper.doors['peer'], zookeeper.doors['election'])


@cached
def create_jmxtrans_image():
    return SourceImage(
        name='jmxtrans',
        parent=Image(namespace='yandex', repository='trusty'),
        scripts=[
            'apt-get -q update && apt-get install -qy openjdk-7-jdk maven && apt-get clean',
            'git clone https://github.com/Naishy/jmxtrans.git',
            'cd jmxtrans && mvn install',
        ],
        files={
            '/root/run.sh': resource_string('jmxtrans.run.sh'),
        },
        volumes={
            'config': '/etc/jmxtrans',
            'logs': '/var/log/jmxtrans',
        },
        entrypoint=['sh'],
        command=['/root/run.sh'],
    )


def create_jmxtrans():
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

    image = create_jmxtrans_image()

    jmxtrans = Container(
        name='zookeeper-jmxtrans',
        image=image,
        volumes={
            'config': ConfigVolume(
                dest=image.volumes['config'],
                files={
                    'zookeeper.json': None,
                },
            ),
            'logs': LogVolume(
                dest=image.volumes['logs'],
                files={
                    'jmxtrans.log': LogFile(),
                },
            ),
        },
        memory=1024**2*512,
    )

    def create_zookeeper_json(jmxtrans=jmxtrans):
        graphite_writers = [{
            '@class': 'com.googlecode.jmxtrans.model.output.GraphiteWriter',
            'settings': {
                'host': door.host,
                'port': door.port,
            },
        } for door in jmxtrans.links['graphites']]

        zkdoor = jmxtrans.links['zookeeper']
        config = {
            'servers': [{
                'host': zkdoor.host,
                'port': zkdoor.port,
                'alias': jmxtrans.ship.name,
                'numQueryThreads': 2,
                'queries': [{
                    'outputWriters': graphite_writers,
                    'obj': 'org.apache.ZooKeeperService:'
                           'name0=ReplicatedServer_id{myid},'
                           'name1=replica.{myid},'
                           'name2=Follower,'
                           'name3=InMemoryDataTree'.format(myid=zkdoor.container.zkid),
                    'attr': datatree_attrs,
                    'oper': datatree_opers,
                }, {
                    'outputWriters': graphite_writers,
                    'obj': 'org.apache.ZooKeeperService:'
                           'name0=ReplicatedServer_id{myid},'
                           'name1=replica.{myid},'
                           'name2=Follower'.format(myid=zkdoor.container.zkid),
                    'attr': follower_attrs,
                }]
            }],
        }
        return JsonFile(config)

    jmxtrans.volumes['config'].files['zookeeper.json'] = create_zookeeper_json

    return jmxtrans


def test(shipment, count):
    shipment.unload_ships()
    zookeepers = []
    for shipnum, ship in enumerate(shipment.ships.values()):
        for i in range(count):
            zookeeper = create_zookeeper()
            zookeeper.name = '{}-{}'.format(zookeeper.name, i)
            ship.place(zookeeper)
            zookeepers.append(zookeeper)

            jmxtrans = create_jmxtrans()
            jmxtrans.name = '{}-{}'.format(jmxtrans.name, i)
            jmxtrans.links['zookeeper'] = zookeeper.doors['jmx']
            jmxtrans.links['graphites'] = []
            ship.place(jmxtrans)

    shipment.expose_ports(range(50000, 50100))

    clusterize_zookeepers(zookeepers)


def build_zookeeper_cluster(ships, memory=1024**3):
    zookeepers = []
    for shipnum, ship in enumerate(ships):
        zookeeper = create_zookeeper(memory=memory)
        ship.place(zookeeper)
        zookeepers.append(zookeeper)

    clusterize_zookeepers(zookeepers)
    return zookeepers


def filter_quorum_ships(ships):
    """Return odd number of ships, one from each datacenter."""
    zooships = [list(dcships)[0] for datacenter, dcships in groupbysorted(ships, lambda s: s.datacenter)]
    if len(zooships) % 2 == 0:
        # If we have even datacenter count, then remove one datacenter from the list
        return zooships[:-1]
    else:
        return zooships


@aslist
def attach_jmxtrans_to_zookeeper(zookeepers, graphites):
    plaindoors = [graphite.doors['plain'] for graphite in graphites]
    for zookeeper in zookeepers:
        jmxtrans = create_jmxtrans()
        jmxtrans.links['zookeeper'] = zookeeper.doors['jmx']
        jmxtrans.links['graphites'] = plaindoors
        zookeeper.ship.place(jmxtrans)
        yield jmxtrans


def create_zkcli_task(zookeepers):
    return Task(
        name='zkcli',
        image=get_zookeeper_image(),
        entrypoint=['/opt/zookeeper/bin/zkCli.sh'],
        command=['-server', zookeepers[0].doors['client'].hostport],
    )
