import argparse
from thor.lib.env import Env


class ParamException(Exception):
    pass

class ParamTypeNotSupportedException(Exception):
    pass


class Param:

    THOR_PARAM_NAMESPACE = '{env}/thor'

    STRING_TYPE = 'String'

    def __init__(self, env):
        self.env = env
        self.__ssm_client = self.env.aws_client('ssm')

    def ssm_client(self):
        return self.__ssm_client

    def get_full_param_name(self, input_name):
        param_env_prefix = '/{}/'.format(self.env.Name())

        if input_name.find(param_env_prefix, 0) == 0:
            param_name = '{name}'.format(
                name=input_name
            )
        else:
            param_name = '/{env}/{name}'.format(
                env=self.env.Name(),
                name=input_name
            )

        return param_name

    def create(self, name, value, param_type=STRING_TYPE):
        return self.create_param(name, value, param_type)

    def create_param(self, name, value, param_type):
        if not param_type == Param.STRING_TYPE:
            raise ParamTypeNotSupportedException()

        param_name = self.get_full_param_name(name)

        try:
            response = self.ssm_client().put_parameter(
                Name=param_name,
                Value=value,
                Type=param_type
            )
            if 'Version' in response:
                return response['Version']
            return False
        except self.ssm_client().exceptions.ParameterAlreadyExists:
            print('Param {} already exist on environment {}'.format(
                param_name,
                self.env.Name()
            ))
        except Exception as err:
            raise Exception('Fail to create parameter with error: {}'.format(
                str(err)
            ))

    def delete(self, name):
        return self.delete_param(name)

    def delete_param(self, name):
        param_name = self.get_full_param_name(name)

        try:
            response = self.ssm_client().delete_parameter(
                Name=param_name
            )
            if response:
                return True
        except self.ssm_client().exceptions.ParameterNotFound:
            return None
        except Exception as err:
            raise Exception('fail to describe parameter with error: {}'.format(
                str(err)
            ))

    def describe(self, name):
        return self.describe_param(name)

    def describe_param(self, name):
        param_name = self.get_full_param_name(name)

        try:
            response = self.ssm_client().get_parameter(
                Name=param_name,
                WithDecryption=False
            )
            return response['Parameter']
        except self.ssm_client().exceptions.ParameterNotFound:
            return None
        except Exception as err:
            raise Exception('fail to describe parameter with error: {}'.format(
                str(err)
            ))

    def get(self, name):
        return self.get_param(name)

    def get_param(self, name):
        param_name = self.get_full_param_name(name)

        try:
            response = self.ssm_client().get_parameter(
                Name=param_name,
                WithDecryption=False
            )
            return response['Parameter']['Value']
        except self.ssm_client().exceptions.ParameterNotFound:
            return None
        except Exception as err:
            print('Something went wrong: {}'.format(str(err)))

    def list(self):
        return self.list_param()

    def list_param(self):
        param_path = '/{env}'.format(
            env=self.env.Name()
        )

        try:
            result_parameters = []
            response = self.ssm_client().get_parameters_by_path(
                Path=param_path,
                Recursive=True,
                WithDecryption=False
            )
            for p in response['Parameters']:
                result_parameters.append(p['Name'])

            while 'NextToken' in response:
                response = self.ssm_client().get_parameters_by_path(
                    Path=param_path,
                    Recursive=True,
                    WithDecryption=False,
                    NextToken=response['NextToken']
                )
                for p in response['Parameters']:
                    result_parameters.append(p['Name'])

            return result_parameters

        except Exception as err:
            print('{}'.format(str(err)))
            exit(-1)

    def update_or_create(self, name, value, param_type=STRING_TYPE):
        if not param_type == Param.STRING_TYPE:
            raise ParamTypeNotSupportedException()

        param_name = self.get_full_param_name(name)

        try:
            response = self.ssm_client().put_parameter(
                Name=param_name,
                Value=value,
                Overwrite=True,
                Type=param_type
            )
            if 'Version' in response:
                return response['Version']
            return False

        except Exception as err:
            raise Exception('Fail to create parameter with error: {}'.format(
                str(err)
            ))

    def update(self, name, value):
        return self.update_param(name, value)

    def update_param(self, name, value):
        param_name = self.get_full_param_name(name)

        try:
            response = self.ssm_client().put_parameter(
                Name=param_name,
                Value=value,
                Overwrite=True
            )
            if 'Version' in response:
                return response['Version']
            return False

        except Exception as err:
            raise Exception('Fail to create parameter with error: {}'.format(
                str(err)
            ))
