import argparse
import logging
from thor.lib.compiler import Compiler
from thor.lib.env import Env
from thor.lib.image import (
    Image,
    ImageInvalidException
)
from thor.lib.packer import Packer
from thor.lib.aws_resources.parameter_store import ParameterStoreException


def build_cmd(args):
    logger = logging.getLogger('BuildCmd')
    logger.info('Building... ')
    packer = Packer()

    try:
        with Image(args.env, args.image, None) as image:
            logger.info('Changing directory to {}'.format(image.get_image_dir()))
            # compiler
            compiler = Compiler(image)
            compiler.build()
            if args.no_image_build:
                logger.info('No image build arg has been provided. Exiting...')
                exit(0)
            # run packer build
            result = packer.run('build', Image.PACKER_FILE)
            logger.info('Return code is {}'.format(result))
            if not result == 0:
                logger.error('Packer build fail')
                exit(Image.BUILD_FAIL_CODE)
            logger.info('Getting latest built artifact...')
            try:
                artifact_id = image.get_manifest_artifact_id()
                region, ami_id = artifact_id.split(':')
            except ValueError:
                logger.error('Invalid manifest ID {}'.format(artifact_id))

            if result == 0:
                logger.info('Build completed with no errors :)')
            else:
                logger.error('Build completed with erros :/')
                exit(Image.BUILD_FAIL_CODE)

            if args.update_latest_ami:
                try:
                    logger.info('Updating build parameters...')
                    image.update_ami_id(ami_id)
                except ParameterStoreException as err:
                    logger.error(str(err))
                    exit(Image.BUILD_FAIL_CODE)
    except ImageInvalidException:
        logger.error(f'Invalid image {args.image}')


def main(args):
    '''
    Build module entry point
    '''
    logger = logging.getLogger('BuildMain')
    build_arg_parser = argparse.ArgumentParser(
        prog='Thor build',
        description='Thor build'
    )
    build_arg_parser.add_argument(
        '--env',
        metavar='ENVIRONMENT',
        required=True,
        type=str,
        help='Environent. Run "thor env list" to show available options.'
    )
    build_arg_parser.add_argument(
        '--image',
        metavar='IMAGE',
        required=True,
        type=str,
        help='Image. Run "thor image --env=$ENV list"'
             'to show available options.'
    )
    build_arg_parser.add_argument(
        '--aws-region',
        metavar='AWS_REGION',
        required=False,
        type=str,
        help='AWS Region'
    )
    build_arg_parser.add_argument(
        '--update-latest-ami',
        action='store_true',
        required=False
    )
    build_arg_parser.add_argument(
        '--no-image-build',
        action='store_true',
        required=False
    )

    args = build_arg_parser.parse_args(args)
    e = Env(args.env)
    e.is_valid_or_exit()
    args.env = e

    if args.aws_region:
        logger.info('Overriding AWS Region with = {}'.format(args.aws_region))
        e.config().set('aws_region', args.aws_region)

    build_cmd(args)
