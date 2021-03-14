import os
import subprocess


def run(cmdline, workdir=None):
    cmd_list = cmdline
    current_dir = os.getcwd()
    output = ''

    if type(cmdline) is not list:
        cmd_list = cmdline.split(' ')

    try:
        if workdir:
            if not os.path.exists(workdir):
                raise Exception('Couldn\'t stat on dir {}'.format(
                    workdir
                ))
            os.chdir(workdir)

        print('Running: {}'.format(
            ' '.join(cmd_list)
        ))
        process = subprocess.Popen(
            cmd_list,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        while process.stdout.readable():
            line = process.stdout.readline()
            if not line:
                break
            output += line.strip()

        if workdir:
            os.chdir(current_dir)

        return output

    except Exception as err:
        print('Error while running command "{cmd}" : {error}'.format(
            cmd=cmdline,
            error=str(err)
        ))


def run_interactive(cmdline, workdir=None):
    cmd_to_run = cmdline
    current_dir = os.getcwd()

    if type(cmdline) is list:
        cmd_to_run = ' '.join(cmdline)

    try:
        if workdir:
            if not os.path.exists(workdir):
                raise Exception('Couldn\'t stat on dir {}'.format(
                    workdir
                ))
            os.chdir(workdir)

        print('Running: {}'.format(cmd_to_run))
        return_code = os.system(cmd_to_run)

        if workdir:
            os.chdir(current_dir)
        return return_code
    except Exception as err:
        print('Error while running command "{cmd}" : {error}'.format(
            cmd=cmd_to_run,
            error=str(err)
        ))
