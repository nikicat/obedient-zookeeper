import setuptools

if __name__ == '__main__':
    setuptools.setup(
        name='obedient.zookeeper',
        version='0.1',
        url='https://github.com/yandex-sysmon/obedient-zookeeper',
        license='GPLv3',
        author='Nikolay Bryskin',
        author_email='devel.niks@gmail.com',
        description='Zookeeper obedient for Dominator',
        platforms='linux',
        packages=['obedient.zookeeper'],
        namespace_packages=['obedient'],
        package_data={'obedient.zookeeper': ['log4j.properties', 'myid', 'zoo.cfg']},
        install_requires=['dominator'],
    )
