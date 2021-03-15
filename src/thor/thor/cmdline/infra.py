import argparse
from thor.lib.env import Env
from thor.lib.terraform import Terraform


def main(args):
    '''
    Infra module entry point
    '''
    infra_arg_parser = argparse.ArgumentParser(
        prog='thor infra',
        description='Thor Infra. This is just an '
                    'alias to run `terraform` using '
                    'correct enviroment.'
    )
    # request env for all parameter operations
    infra_arg_parser.add_argument(
        '--env',
        metavar='ENVIRONMENT',
        required=True,
        type=str,
        help='Environent. Run "thor env list" to show available options.'
    )

    args, terraform_args = infra_arg_parser.parse_known_args(args)
    e = Env(args.env)
    e.is_valid_or_exit()

    if 'env' in args:
        terraform = Terraform()
        terraform.run(*terraform_args)
    else:
        infra_arg_parser.print_usage()
        exit(-1)
