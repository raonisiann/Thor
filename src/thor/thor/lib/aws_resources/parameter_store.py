from thor.lib.aws_resources.aws_resource import AwsResource


class ParameterStoreNotFoundException(Exception):
    pass


class ParameterStoreAlreadyExistsException(Exception):
    pass


class ParameterStoreException(Exception):
    pass


class ParameterStoreUnsupportedParamTypeException(Exception):
    pass


class ParameterStore(AwsResource):

    STRING_TYPE = 'String'
    STRING_LIST_TYPE = 'StringList'
    SECURE_STRING_TYPE = 'SecureString'

    def __init__(self, env):
        super().__init__('ssm', env, alias='parameter')

    def __put_parameter(self, name, value, param_type, overwrite):
        try:
            self.client().put_parameter(
                Name=name,
                Value=value,
                Type=param_type,
                Overwrite=overwrite,
                Tier='Standard'
            )
        except self.client().exceptions.ParameterAlreadyExists:
            raise ParameterStoreAlreadyExistsException(name)
        except (self.client().exceptions.InternalServerError,
                self.client().exceptions.InvalidKeyId,
                self.client().exceptions.ParameterLimitExceeded,
                self.client().exceptions.TooManyUpdates,
                self.client().exceptions.HierarchyLevelLimitExceededException,
                self.client().exceptions.HierarchyTypeMismatchException,
                self.client().exceptions.InvalidAllowedPatternException,
                self.client().exceptions.ParameterMaxVersionLimitExceeded,
                self.client().exceptions.ParameterPatternMismatchException,
                self.client().exceptions.UnsupportedParameterType,
                self.client().exceptions.PoliciesLimitExceededException,
                self.client().exceptions.InvalidPolicyTypeException,
                self.client().exceptions.InvalidPolicyAttributeException,
                self.client().exceptions.IncompatiblePolicyException) as err:
            raise ParameterStoreException(str(err))

    def create(self, name, value, param_type=STRING_TYPE):
        self.logger.info('Creating {}'.format(name))
        self.__put_parameter(name, value, param_type, overwrite=False)

    def destroy(self, name):
        try:
            self.logger.info('Destroying {}'.format(name))
            self.client().delete_parameter(
                Name=name
            )
            self.logger.info('{} destroyed.'.format(name))
        except self.client().exceptions.ParameterNotFound:
            raise ParameterStoreNotFoundException()

    def read(self, name, with_decryption=False):
        try:
            self.logger.info('Reading {}'.format(name))
            response = self.client().get_parameter(
                Name=name,
                WithDecryption=with_decryption
            )
            if 'Parameter' in response:
                return response['Parameter']
            else:
                return None
        except self.client().exceptions.ParameterNotFound:
            raise ParameterStoreNotFoundException()

    def get(self, name):
        parameter = self.read(name)
        if 'Value' in parameter:
            if parameter['Type'] == ParameterStore.STRING_LIST_TYPE:
                return parameter['Value'].split(',')
            if parameter['Type'] == ParameterStore.STRING_TYPE:
                return parameter['Value']
            if parameter['Type'] == ParameterStore.SECURE_STRING_TYPE:
                raise ParameterStoreUnsupportedParamTypeException()
        else:
            return None

    def list(self, path):
        try:
            response = self.tokenized(
                self.client().get_parameters_by_path,
                'Parameters',
                Path=path,
                Recursive=True,
                WithDecryption=False
            )
            return response
        except (self.client().exceptions.InternalServerError,
                self.client().exceptions.InvalidFilterKey,
                self.client().exceptions.InvalidFilterOption,
                self.client().exceptions.InvalidFilterValue,
                self.client().exceptions.InvalidKeyId) as err:
            raise ParameterStoreException(str(err))

    def update(self, name, value, param_type=STRING_TYPE):
        self.logger.info('Updating {}'.format(name))
        self.__put_parameter(name, value, param_type, overwrite=True)

    def update_or_create(self, name, value, param_type):
        self.logger.info('Updating (overwrite=true) {}'.format(name))
        self.__put_parameter(name, value, param_type, overwrite=True)
