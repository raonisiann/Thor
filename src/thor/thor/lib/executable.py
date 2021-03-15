import os
import requests
from thor.lib import cmd
from thor.lib.base import Base


class ExecutableException(Exception):
    pass


class ExecutableDownloadAlreadyExists(Exception):
    pass


class Executable(Base):

    def __init__(self, exec_name, install_dir, download_url):
        super().__init__()
        self.exec_name = exec_name
        self.install_dir = install_dir
        self.download_url = download_url

    def download(self, dest_dir, overwrite=False):
        try:
            res = requests.get(self.download_url, allow_redirects=True)
        except Exception as err:
            raise Exception('Fail to download %s with error: %s',
                            self.exec_name, str(err))

        download_file = '{dir}/{file_name}'.format(
            dir=dest_dir,
            file_name=self.exec_name
        )

        if os.path.exists(download_file) and overwrite:
            return download_file

        with open(download_file, 'wb') as download:
            try:
                download.write(res.content)
            except Exception as err:
                self.logger.error('Unable to download %s with error %s',
                                  download_file, str(err))
        return download_file

    def get_exec_path(self):
        return '{install_dir}/{exec_name}'.format(
            install_dir=self.install_dir,
            exec_name=self.exec_name
        )

    def run(self, *args):
        executable_cmd = [
            '{exec_bin}'.format(exec_bin=self.get_exec_path()),
        ]
        if args:
            for arg in args:
                executable_cmd.append(arg)
        self.logger.info('Running {}'.format(' '.join(executable_cmd)))
        result = cmd.run_interactive(executable_cmd)
        self.logger.info('Return code is {}'.format(result))
        return result
