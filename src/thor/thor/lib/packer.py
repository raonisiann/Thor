import os


class PackerException(Exception):
    pass


class Packer:

    def __init__(self):
        self.exec_path = None

    def get_exec_path(self):
        if self.exec_path is None:
            self.exec_path = '{base_dir}/bin/packer'.format(
                base_dir=os.getcwd()
            )
            if not os.path.exists(self.exec_path):
                raise PackerException(
                    'unable to locate packer under {}'.format(
                        os.getcwd()
                    )
                )
        return self.exec_path
