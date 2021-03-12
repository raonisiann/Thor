import argparse


def deploy_cmd(args):
    logger = logging.getLogger('DeployCommand')
    logger.info('Starting...')
    image = Image(env=args.env, name=args.image)

    with DeployLock(image):
        deploy = DeployBlueGreen(image)
        exit()
        try:
            latest_ami_param = img.get_latest_ami_built_param()
            latest_ami_region_param = img.get_latest_ami_region_param()
            asg_name_param = img.get_asg_name()

            latest_ami_id = ps.get_param(latest_ami_param)
            latest_ami_region = ps.get_param(latest_ami_region_param)
            asg_name = ps.get_param(asg_name_param)

            if not latest_ami_id:
                raise DeployException('Could not get latest AMI')

            if not asg_name:
                raise DeployException('Could not get Auto Scaling group')

            print('{} = {}'.format(latest_ami_param, latest_ami_id))
            print('{} = {}'.format(latest_ami_region_param, latest_ami_region))
            print('{} = {}'.format(asg_name_param, asg_name))

        except Exception as err:
            raise DeployException('Fail to get params with error: {}'.format(
                str(err)
            ))

        try:
            deploy = Deploy(img)
            # do blue/green deploy
            new_asg_name = deploy.do_blue_green_deploy(
                image=img.get_name(),
                ami_id=latest_ami_id,
                asg_name=asg_name
            )
            print('Updating AutoScaling group name...')
            ps.update_param(asg_name_param, new_asg_name)
            print('DEPLOY DONE.')
        except DeployException as err:
            print('Deploy FAIL with error: {}'.format(
                str(err)
            ))
            exit(-1)


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
        e.set_config('aws_region', args.aws_region)
    if args.ami_id:
        logger.info('Overriding AMI ID with = {}'.format(args.ami_id))
        e.set_config('auto_scaling_settings.ami_id', args.ami_id)
    if args.autoscaling_name:
        logger.info('Overriding AutoScaling group name with = {}'.format(args.autoscaling_name))
        e.set_config('auto_scaling_settings.autoscaling_name', args.autoscaling_name)
    # inject environment object on arguments
    args.env = e
    # run deploy
    deploy_cmd(args)
