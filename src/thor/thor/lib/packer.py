from pathlib import Path
from thor.lib.executable import Executable


class PackerException(Exception):
    pass


class Packer(Executable):

    def __init__(self):
        super().__init__(
            'packer',
            '{home}/.local/bin'.format(home=Path.home()),
            'https://releases.hashicorp.com/packer/1.6.5/packer_1.6.5_linux_amd64.zip'
        )
