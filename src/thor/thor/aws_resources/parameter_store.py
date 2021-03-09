from thor.aws_resources.aws_resource import AwsResource


class ParameterStoreNotFoundException(Exception):
    pass


class ParameterStoreAlreadyExistsException(Exception):
    pass


class ParameterStoreException(Exception):
    pass


class ParameterStore(AwsResource):

    STRING_TYPE = 'String'

    def __init__(self, env):
        super().__init__('ssm', env)

    def __parse_params(self, params):
        parsed_config = {}
        if 'name' in params:
            parsed_config['Name'] = params['name']
        if 'value' in params:
            parsed_config['Value'] = params['value']
        if 'param_type' in params:
            parsed_config['Type'] = params['param_type']
        if 'with_decryption' in params:
            parsed_config['WithDecryption'] = params['with_decryption']
        if 'overwrite' in params:
            parsed_config['Overwrite'] = params['overwrite']
        if 'recursive' in params:
            parsed_config['Recursive'] = params['recursive']
        return parsed_config

    def create(self, name, value, param_type=STRING_TYPE):
        self.update(name, value, param_type, overwrite=False)

    def destroy(self, name):
        saved_params = locals()
        try:
            response = self.client().delete_parameter(
                self.__parse_params(saved_params)
            )
        except self.client().exceptions.ParameterNotFound:
            raise ParameterStoreNotFoundException()

    def read(self, name):
        saved_params = locals()
        try:
            response = self.client().get_parameter(
                self.__parse_params(saved_params)
            )
            if 'Parameter' in response:
                return response['Parameter']
            else:
                return None
        except self.client().exceptions.ParameterNotFound:
            raise ParameterStoreNotFoundException()

    def get(self, name):
        saved_params = locals()
        try:
            response = self.client().get_parameter(
                self.__parse_params(saved_params)
            )
            if 'Parameter' in response:
                return response['Parameter']['Value']
            else:
                return None
        except self.client().exceptions.ParameterNotFound:
            raise ParameterStoreNotFoundException()

    def list(self):
        param_path = '/{env}'.format(
            env=self.env.Name()
        )
        try:
            response = self.tokenized(
                self.client().get_parameters_by_path,
                'Parameters',
                Path=param_path,
                Recursive=True,
                WithDecryption=False
            )
            return response
        except (self.client().exceptions.InternalServerError,
                self.client().exceptions.InvalidFilterKey,
                self.client().exceptions.InvalidFilterOption,
                self.cient().exceptions.InvalidFilterValue,
                self.client().exceptions.InvalidKeyId) as err:
            raise ParameterStoreException(str(err))

    def update(self, name, value, param_type=STRING_TYPE, overwrite=False):
        saved_params = locals()
        try:
            response = self.client().put_parameter(
                self.__parse_params(saved_params)
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

    def update_or_create(self, name, value, param_type):
        self.update(name, value, param_type, overwrite=True)
