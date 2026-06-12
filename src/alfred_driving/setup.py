import os
from glob import glob

from setuptools import find_packages, setup

package_name = 'alfred_driving'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'config'), glob('config/*')),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
        (os.path.join('share', package_name, 'resource', 'map'), glob('resource/map/*')),
        (os.path.join('share', package_name, 'resource', 'marker'), glob('resource/marker/*')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='ROKEY 7기 지능1 Team Alfred',
    maintainer_email='sunq0726@gmail.com',
    description='Web-driven normal/blind person dispatch for robot2/robot4.',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'navigation_node = alfred_driving.navigation_node:main',
            'patrol_node = alfred_driving.patrol_node:main',
            'behavior_node = alfred_driving.behavior_node:main',
            'aruco_tracker_node = alfred_driving.aruco_tracker_node:main',
            'marker_speed_governor = alfred_driving.marker_speed_governor:main',
            'rosbridge_node = alfred_driving.rosbridge_node:main',
            'server_request_node = alfred_driving.server_request_node:main',
            'scenario_manager_node = alfred_driving.scenario_manager_node:main',
        ],
    },
)
