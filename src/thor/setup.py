from setuptools import (
    setup,
    find_packages
)
from thor.__version__ import __version__

setup(
    name='thor',
    description='Thor Infrastructure Tools',
    author='Raoni Sian',
    author_email='raonisiann@live.com',
    home_page='https://github.com/raonisiann/Thor',
    version=__version__,
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'thor = thor.main:run'
        ]
    }
)
