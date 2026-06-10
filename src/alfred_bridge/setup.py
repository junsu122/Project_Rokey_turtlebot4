import os
from glob import glob

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
        (os.path.join('share', package_name, 'config'), glob('config/*.yaml')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='ROKEY 7기 지능1 Team Alfred',
    maintainer_email='sunq0726@gmail.com',
    description='로봇 상태 머신 + 분산 릴레이 에스코트 두뇌 노드',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'robot2_manager = alfred_bridge.robot2_manager:main',
            'robot4_manager = alfred_bridge.robot4_manager:main',
            'all_robot_manager = alfred_bridge.all_robot_manager:main',
            'fake_robot = alfred_bridge.fake_robot:main',
            'escort_state_bridge_node = alfred_bridge.escort_state_bridge_node:main',
            'state_ws_bridge_node = alfred_bridge.state_ws_bridge_node:main',
            'robot_state_publisher_node = alfred_bridge.robot_state_publisher_node:main',
        ],
    },
)
