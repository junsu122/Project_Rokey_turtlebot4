from setuptools import find_packages, setup

package_name = 'alfred_vision'

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
    description='비전 트랙: yolo_monitor_node, video_sender_node',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'yolo_monitor_node = alfred_vision.yolo_monitor_node:main',
            'video_sender_node = alfred_vision.video_sender_node:main',
        ],
    },
)
