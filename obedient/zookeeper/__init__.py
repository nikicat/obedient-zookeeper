from pkg_resources import resource_string
import os
from dominator import *

def create(
    ships=[LocalShip()],
    memory=1024**3,
    snap_count=os.environ.get('OBEDIENT_ZOOKEEPER_SNAP_COUNT', 10000),
    global_outstanding_limit=os.environ.get('OBEDIENT_ZOOKEEPER_GLOBAL_OUTSTANDING_LIMIT', 1000),
):
    containers = []

    config = ConfigVolume(
        dest='/opt/zookeeper/conf',
        files = [
            TemplateFile(
                TextFile('zoo.cfg'),
                containers=containers,
                snap_count=snap_count,
                global_outstanding_limit=global_outstanding_limit,
            ),
            TextFile('log4j.properties'),
        ]
    )

    image = Image(repository='yandex/zookeeper', tag='latest')

    containers.extend([
        Container(
            name='zookeeper',
            ship=ship,
            image=image,
            volumes=[
                DataVolume(
                    dest='/var/lib/zookeeper',
                    path='/var/lib/zookeeper',
                ),
                config,
            ],
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
