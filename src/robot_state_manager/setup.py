from setuptools import find_packages, setup

package_name = 'robot_state_manager'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools', 'paho-mqtt'],
    zip_safe=True,
    maintainer='junsu',
    maintainer_email='handjun2580@gmail.com',
    description='FMS task(IF-03) 기반 로봇 상태 머신 — robot2/robot4 (MQTT 직접 연동)',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'robot2_state_manager = robot_state_manager.robot2_state_manager:main',
            'robot4_state_manager = robot_state_manager.robot4_state_manager:main',
        ],
    },
)
