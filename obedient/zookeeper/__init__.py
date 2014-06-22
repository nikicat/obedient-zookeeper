from pkg_resources import resource_string
from dominator import *

def make_containers(ships):
    containers = []

    config = ConfigVolume(
        dest='/opt/zookeeper/conf',
        files = [
            TemplateFile(TextFile('zoo.cfg'), containers=containers),
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
            memory=1024**3,
            env={
                'JAVA_OPTS': '-Xmx700m',
                'JAVA_RMI_SERVER_HOSTNAME': ship.fqdn,
                'VISUALVM_DISPLAY_NAME': '{}-{}'.format(ship.name, 'zookeeper'),
                'ZOOKEEPER_MYID': str(myid),
            },
        ) for myid, ship in enumerate(ships, 1)])
    return containers
