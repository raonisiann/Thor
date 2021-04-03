import argparse
from thor.lib.packer import Packer
from thor.lib.image import Image


def build_cmd(args):
    print('Building... ')
    packer_exec = Packer().get_exec_path()

    with Image(args.env, args.image, None) as img:
        print('Changing directory to {}'.format(img.get_image_dir()))
        # $ packer build TEMPLATE
        packer_cmd = [
            '{packer_exec}'.format(packer_exec=packer_exec),
            'build',
            '{}'.format(Image.PACKER_FILE)
        ]
        # run packer build
        result = cmd.run_interactive(packer_cmd)
        print('Build return code ===>>> {}'.format(result))

        if result == 0:
            if args.update_latest_ami:
                print('Updating parameter store...')
                print('Getting latest built artifact...')
                try:
                    artifact_id = img.get_manifest_artifact_id()
                    region, ami_id = artifact_id.split(':')
                except ValueError:
                    print('BUILD ERROR: Invalid manifest ID ==> {}'.format(
                        artifact_id
                    ))

                ami_id_param = img.get_latest_ami_built_param()
                region_param = img.get_latest_ami_region_param()

                ps = Param(args.env)

                try:
                    print('Updating --> {}'.format(ami_id_param))
                    ps.update_param(ami_id_param, ami_id)
                    print('Updating --> {}'.format(region_param))
                    ps.update_param(region_param, region)
                except Exception as err:
                    print('Param update FAIL with error: {}'.format(
                        str(err)
                    ))
                    exit(Image.BUILD_FAIL_CODE)
            print('BUILD FINISHED WITH SUCCESS')
        else:
            print('BUILD FINISHED WITH ERRORS')
            exit(Image.BUILD_FAIL_CODE)


def describe_cmd(args):
    pass


def generate_cmd(args):
    print('Generating settings...', file=sys.stderr)
    aws_filters = ''
    env = args.env

    if 'filters' in args:
        aws_filters = args.filters

    ami_finder = AwsAmiFinder(env.get_config().get('aws_region'))
    latest_image = ami_finder.get_latest_image(aws_filters)
    if latest_image:
        img = Image(env, args.image, latest_image)
        print('Packer file ===============')
        print(img.generate_packer_file())
        print('Pre-Provisioner script ========')
        print(img.generate_pre_provisioner_file())
        print('Post-Provisioner script ========')
        print(img.generate_post_provisioner_file())
        print('Instance launch script ====')
        print(img.generate_instance_launch_script())
    else:
        print('No images found with selected filters.')


def main(args):
    '''
    Image module entry point
    '''
    ami_arg_parser = argparse.ArgumentParser(
        prog='Automator image',
        description='Automator AWS Image Manager'
    )

    # request env for all parameter operations
    ami_arg_parser.add_argument(
        '--env',
        metavar='ENVIRONMENT',
        required=True,
        type=str,
        help='Environent. Run "thor env list" to show available options.'
    )
    # request image for all parameter operations
    ami_arg_parser.add_argument(
        '--image',
        metavar='IMAGE',
        required=True,
        type=str,
        help='Image. Run "thor image --env=$ENV list"'
             'to show available options.'
    )
    # allow set aws region if unable to auto detect
    ami_arg_parser.add_argument(
        '--aws-region',
        metavar='AWS_REGION',
        required=False,
        type=str,
        help='AWS Region'
    )
    # allow set ami filters to AMI lookup
    ami_arg_parser.add_argument(
        '--filters',
        metavar='name=value[,name=value]',
        required=False,
        type=str,
        help='AMI Filters for image lookup. Format: key=value'
             'If multiple filters use comma: a=1,b=2'
    )

    subparsers = ami_arg_parser.add_subparsers()
    # build sub-command
    build_subparser = subparsers.add_parser(
        'build',
        help='image build ENV',
        usage='image build ENV'
    )
    build_subparser.add_argument(
        '--update-latest-ami',
        action='store_true',
        required=False
    )
    build_subparser.set_defaults(func=build_cmd)
    # describe sub-command
    describe_subparser = subparsers.add_parser(
        'describe',
        help='Describe settings on Packer',
        usage='Describe action must be either current or backup.',
    )
    describe_subparser.set_defaults(func=describe_cmd)
    # generate sub-command
    generate_subparser = subparsers.add_parser(
        'generate',
        help='Generate new Packer configuration based on entered arguments'
    )
    generate_subparser.add_argument(
        '--write',
        help='Write generated content in the packer file.'
             'Backups the existing one.'
    )
    generate_subparser.set_defaults(func=generate_cmd)

    args = ami_arg_parser.parse_args(args)
    e = Env(args.env)
    e.is_valid_or_exit()

    if args.aws_region:
        print('Overriding AWS Region with = {}'.format(args.aws_region))
        e.config().set('aws_region', args.aws_region)

    if 'func' in args:
        args.env = e
        args.func(args)
    else:
        ami_arg_parser.print_usage()
        exit(-1)
