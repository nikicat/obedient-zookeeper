import setuptools

if __name__ == '__main__':
    setuptools.setup(
        name='obedient.zookeeper',
        version='3.1.0',
        url='https://github.com/yandex-sysmon/obedient.zookeeper',
        license='LGPLv3',
        author='Nikolay Bryskin',
        author_email='devel.niks@gmail.com',
        description='Zookeeper obedient for Dominator',
        platforms='linux',
        packages=['obedient.zookeeper'],
        namespace_packages=['obedient'],
        package_data={'obedient.zookeeper': [
            'log4j.properties',
            'run.sh',
            'jmxtrans.run.sh',
        ]},
        entry_points={'obedient': [
            'test = obedient.zookeeper:test',
        ]},
        install_requires=['dominator[full] >=15.1a'],
    )
