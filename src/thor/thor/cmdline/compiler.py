import argparse
import logging
from thor.lib.compiler import Compiler
from thor.lib.env import Env
from thor.lib.image import Image


def compiler_cmd(args):
    logger = logging.getLogger('CompileCommand')
    logger.info('Starting...')
    image = Image(env=args.env, name=args.image)

    compiler = Compiler(image)

    if args.target is not None:
        build_targets_names = [
            x['name'] for x in compiler.build_targets]
        if args.target in build_targets_names:
            for target in compiler.build_targets:
                if target['name'] == args.target:
                    build_target_func = target['func']
                    break
            result = build_target_func()
        else:
            build_target_str = ', '.join(build_targets_names)
            logger.error(f'Compiler target must be either {build_target_str}')
            result = 'fail'
    else:
        result = compiler.build_all()

    if result == 'success':
        logger.info('Completed with no errors :) ')
    elif result == 'fail':
        logger.info('Build fail :(')
    else:
        logger.error('Build not returned any expected result. :(')


def main(args):
    '''
    Compiler module entry point
    '''
    compiler_arg_parser = argparse.ArgumentParser(
        prog='Thor compiler',
        description='Thor compiler'
    )

    # request env for all parameter operations
    compiler_arg_parser.add_argument(
        '--env',
        metavar='ENVIRONMENT',
        required=True,
        type=str,
        help='Environent. Run "thor env list" to show available options.'
    )
    # request image for all parameter operations
    compiler_arg_parser.add_argument(
        '--image',
        metavar='IMAGE',
        required=True,
        type=str,
        help='Image. Run "thor image --env=$ENV list"'
             'to show available options.'
    )

    # request image for all parameter operations
    compiler_arg_parser.add_argument(
        '--target',
        metavar='TARGET',
        required=False,
        type=str,
        help='Compiler targets: all (default), static, '
             'templates, config and packer'
    )

    args = compiler_arg_parser.parse_args(args)
    e = Env(args.env)
    e.is_valid_or_exit()

    # inject environment object on arguments
    args.env = e
    # run deploy
    compiler_cmd(args)
