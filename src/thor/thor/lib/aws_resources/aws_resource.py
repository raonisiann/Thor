import logging
import time


class AwsResourceKeyException(Exception):
    pass


class AwsResourceTimeoutException(Exception):
    pass


class AwsResourceParameterException(Exception):
    pass


class AwsResource:

    MAX_RETRY_INTERVAL_SECONDS = 60
    MAX_TIMEOUT_SECONDS = 1800
    MIN_RETRY_INTERVAL_SECONDS = 1
    MIN_TIMEOUT_SECONDS = 1

    def __init__(self, client_name, env, alias=None):
        self.client_name = client_name
        self.env = env
        self.alias = alias
        self.__client = None
        if alias is None:
            self.alias = self.client_name
        self.logger = logging.getLogger('Resource.{}'.format(self.alias))

    def __translate_dict_to_boto3_config(self, old):
        new = {}
        for k, v in old.items():
            new_key = self.__translate_to_aws_config_names(k)
            if type(v) is dict:
                new[new_key] = self.__translate_dict_to_boto3_config(v)
            elif type(v) is list:
                print('list')
                new[new_key] = []
                for item in v:
                    if type(item) is dict:
                        new[new_key].append(
                            self.__translate_dict_to_boto3_config(item))
                    else:
                        new[new_key].append(item)
            else:
                if len(str(v)):
                    new[new_key] = v
        return new

    def __translate_to_aws_config_names(self, name):
        translated = []
        i = 0
        while i < len(name):
            if i == 0:
                translated.append(name[0].upper())
            elif name[i] == '_':
                translated.append(name[i+1].upper())
                i += 1
            else:
                translated.append(name[i])
            i += 1
        return ''.join(translated)

    def translate_dict_to_aws_config_names(self, input_dict):
        return self.__translate_dict_to_boto3_config(input_dict)

    def sanitize_dict(self, input_dict):
        '''
        Remove keys that have empty values like
        empty strings, lists and dict. 'None' is
        also removed.
        '''
        sanitized = {}
        if input_dict:
            for k, v in input_dict.items():
                if v:
                    sanitized[k] = v
                if type(v) is int:
                    sanitized[k] = v
                if type(v) is bool:
                    sanitized[k] = v
        return sanitized

    def client(self):
        if self.__client is None:
            self.__client = self.env.aws_client(self.client_name)
        return self.__client

    def output_status(self, status):
        '''
        Output Resource current status to /dev/stdout
        '''
        print('[{resource_group}] {status}'.format(
            resource_group=self.alias.upper(),
            status=status
        ))

    def tokenized(self, func, key, *args, **kwargs):
        results = []
        response = func(*args, **kwargs)

        if response and key not in response:
            raise AwsResourceKeyException(
                '{} does not exist in response'.format(key)
            )
        [results.append(v) for v in response[key] if v]

        while 'NextToken' in response and response['NextToken']:
            response = func(NextToken=response['NextToken'], **kwargs)
            [results.append(v) for v in response[key] if v]
        return results

    def wait_for(self, retry_interval, timeout, func, *args, **kwargs):
        '''
        Wait until the resource reaches a particular states. That happens
        by checking the result of 'func'. The cycle ends when 'func' returns
        a 'True' logical value.

        Parameters:
            retry_interval (int): Retry interval in seconds between calls to 'func'.
            timeout (int): Max time in seconds that 'func' has to return True.
            func (callable): Callable object
            args (*args): 'func' positional args
            kwargs (**kwargs): 'func' key word args

        Returns:
            bool: True if 'func' ends before the timeout
        '''
        if retry_interval < AwsResource.MIN_RETRY_INTERVAL_SECONDS or retry_interval > AwsResource.MAX_RETRY_INTERVAL_SECONDS:
            raise AwsResourceParameterException(
                'Invalid retry_interval value must be => {} and <= {}'.format(
                    AwsResource.MIN_RETRY_INTERVAL_SECONDS,
                    AwsResource.MAX_RETRY_INTERVAL_SECONDS
                )
            )
        if timeout < AwsResource.MIN_TIMEOUT_SECONDS or timeout > AwsResource.MAX_TIMEOUT_SECONDS:
            raise AwsResourceParameterException(
                'Invalid timeout value must be => {} and <= {}'.format(
                    AwsResource.MIN_TIMEOUT_SECONDS,
                    AwsResource.MAX_TIMEOUT_SECONDS
                )
            )
        time_start = time.time()
        while True:
            try:
                result = func(*args, **kwargs)
            except Exception as ex:
                raise ex
            if result:
                break
            if int(time.time() - time_start) >= timeout:
                raise AwsResourceTimeoutException(
                    'Function {} timed out after {} seconds'.format(
                        func.__name__,
                        timeout
                    )
                )
            self.logger.info('Waiting %s seconds for next attempt...',
                             retry_interval)
            time.sleep(retry_interval)
        return True
