from pathlib import Path
from thor.lib.executable import Executable


class TerraformException(Exception):
    pass


class Terraform(Executable):

    def __init__(self):
        super().__init__(
            'terraform',
            '{home}/.local/bin'.format(home=Path.home()),
            'https://releases.hashicorp.com/terraform/0.14.0/terraform_0.14.0_linux_amd64.zip'
        )
