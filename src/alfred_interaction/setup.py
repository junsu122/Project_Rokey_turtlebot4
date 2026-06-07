from setuptools import find_packages, setup

package_name = 'alfred_interaction'

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
    description='고객 응대 트랙: STT/LLM/TTS/UI 노드',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'ui_node = alfred_interaction.ui_node:main',
            'stt_node = alfred_interaction.stt_node:main',
            'llm_node = alfred_interaction.llm_node:main',
            'tts_node = alfred_interaction.tts_node:main',
        ],
    },
)
