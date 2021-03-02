

class AwsResource:

    def __init__(self, name, env):
        self.name = name
        self.env = env
        self.__client = None

    def client(self):
        if self.__client is None:
            self.__client = self.env.aws_client(name)
        return self.__client

    def output_status(self, status):
    """
    Output Resource current status to /dev/stdout
    """
        print('[{resource_group}] {status}'.format(
            resource_group=self.name,
            status=status
        ))