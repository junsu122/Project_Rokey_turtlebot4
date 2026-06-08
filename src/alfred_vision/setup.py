from setuptools import find_packages, setup
from glob import glob
import os

package_name = 'alfred_vision'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'resource'),
            glob('resource/*.pt')),
        (os.path.join('share', package_name, 'config'),
            glob('config/*.yaml')),
        (os.path.join('share', package_name, 'launch'),
            glob('launch/*.py')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='ROKEY 7기 지능1 Team Alfred',
    maintainer_email='sunq0726@gmail.com',
    description='비전 트랙: YOLO 감지, 이벤트 핸들러',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'detector      = alfred_vision.detector_node:main',
            'event_handler = alfred_vision.event_handler_node:main',
        ],
    },
)
