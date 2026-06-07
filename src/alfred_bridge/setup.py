from setuptools import find_packages, setup

package_name = 'alfred_bridge'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='ROKEY 7기 지능1 Team Alfred',
    maintainer_email='sunq0726@gmail.com',
    description='ROS ↔ MQTT/IF 양방향 번역 브리지 노드',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'fms_bridge_node = alfred_bridge.fms_bridge_node:main',
        ],
    },
)
