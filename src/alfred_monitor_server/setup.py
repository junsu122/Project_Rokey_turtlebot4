import os
from glob import glob
from setuptools import find_packages, setup

package_name = 'alfred_monitor_server'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    package_data={
        package_name: [
            'web/**/*',
            'web/*',
            'viz_3d/**/*',
            'viz_3d/*',
            'poi_table.yaml',
        ],
    },
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='ROKEY 7기 지능1 Team Alfred',
    maintainer_email='sunq0726@gmail.com',
    description='로봇 상태 모니터링 서버 — Flask API + ROS2 ingest',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'server = alfred_monitor_server.main:main',
        ],
    },
)
