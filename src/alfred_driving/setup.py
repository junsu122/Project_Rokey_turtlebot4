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
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='ROKEY 7기 지능1 Team Alfred',
    maintainer_email='sunq0726@gmail.com',
    description='주행/에스코트 트랙: behavior_node + nav2/localization 설정',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'behavior_node = alfred_driving.behavior_node:main',
            'escort_node = alfred_driving.escort_node:main',
            'navigation_node = alfred_driving.navigation_node:main',
            'patrol_node = alfred_driving.patrol_node:main',
            'rosbridge_node = alfred_driving.rosbridge_node:main',
            'web_request_node = alfred_driving.web_request_node:main',
        ],
    },
)
