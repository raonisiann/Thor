import argparse
import logging
from thor.lib.deploy import DeployBlueGreen
from thor.lib.compiler import Compiler
from thor.lib.env import Env
from thor.lib.image import Image


def deploy_cmd(args):
    logger = logging.getLogger('DeployCommand')
    logger.info('Starting...')
    image = Image(env=args.env, name=args.image)

    with Compiler(image):
        deploy = DeployBlueGreen(image)
        result = deploy.run()

    if result == 'success':
        logger.info('Completed with no errors :)')
    elif result == 'cancelled':
        logger.info('Cancelled')
    elif result == 'fail':
        logger.error('Deploy fail')


def main(args):
    '''
    Deploy module entry point
    '''
    logger = logging.getLogger('DeployMain')
    deploy_arg_parser = argparse.ArgumentParser(
        prog='Thor deploy',
        description='Thor deploy'
    )

    # request env for all parameter operations
    deploy_arg_parser.add_argument(
        '--env',
        metavar='ENVIRONMENT',
        required=True,
        type=str,
        help='Environent. Run "thor env list" to show available options.'
    )
    # request image for all parameter operations
    deploy_arg_parser.add_argument(
        '--image',
        metavar='IMAGE',
        required=True,
        type=str,
        help='Image. Run "thor image --env=$ENV list"'
             'to show available options.'
    )
    # allow to set aws region for all parameter operations
    deploy_arg_parser.add_argument(
        '--aws-region',
        metavar='AWS_REGION',
        required=False,
        type=str,
        help='AWS Region'
    )
    # allow to set ami-id to force deploy of specific image
    deploy_arg_parser.add_argument(
        '--ami-id',
        metavar='AMI_ID',
        required=False,
        type=str,
        help='AWS AMI (Amazon Machine Image) id'
    )
    # allow to set auto-scaling group name
    deploy_arg_parser.add_argument(
        '--autoscaling-name',
        metavar='AUTOSCALING_NAME',
        required=False,
        type=str,
        help='Name of AutoScaling group configuration will be copied'
    )

    args = deploy_arg_parser.parse_args(args)
    e = Env(args.env)
    e.is_valid_or_exit()

    if args.aws_region:
        logger.info('Overriding AWS Region with = {}'.format(args.aws_region))
        e.config().set('aws_region', args.aws_region)
    if args.ami_id:
        logger.info('Overriding AMI ID with = {}'.format(args.ami_id))
        e.config().set('launch_template.image_id', args.ami_id)
    if args.autoscaling_name:
        logger.info('Overriding AutoScaling group name with = {}'.format(
                    args.autoscaling_name))
        e.config().set('scaling.auto_scaling_group_name',
                       args.autoscaling_name)
    # inject environment object on arguments
    args.env = e
    # run deploy
    deploy_cmd(args)
