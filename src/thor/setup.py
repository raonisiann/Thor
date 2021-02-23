from setuptools import (
    setup,
    find_packages
)

setup(
    name='thor',
    description='Thor Infrastructure Tools',
    author='Raoni Sian',
    author_email='raonisiann@live.com',
    version='0.1',
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'thor = thor.main:run'
        ]
    }
)
