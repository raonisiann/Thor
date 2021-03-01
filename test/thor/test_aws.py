from unittest import TestCase
from thor.aws import Aws, AwsClientException


class TestAws(TestCase):

    def test_with_tokenized_method_no_next_token(self):
        test_return = {
            'first_return': {
                'Test': [
                    {
                        'test_key': 'test_value'
                    }
                ]
            }
        }
        return_iter = iter(test_return)

        def fake_call(**kwargs):
            try:
                key = next(return_iter)
                return test_return[key]
            except StopIteration:
                return {}

        result = Aws.with_tokenized_method(fake_call, 'Test')
        self.assertListEqual(result, [{'test_key': 'test_value'}])

    def test_with_tokenized_method_next_token(self):
        test_return = {
            'first_return': {
                'Test': [
                    {
                        'test_key': 'test_value'
                    }
                ],
                'NextToken': '1234567890'
            },
            'second_return': {
                'Test': [
                    {
                        'test_key_2': 'test_value_2'
                    }
                ]
            }
        }
        return_iter = iter(test_return)

        def fake_call(**kwargs):
            try:
                key = next(return_iter)
                return test_return[key]
            except StopIteration:
                return {}

        result = Aws.with_tokenized_method(fake_call, 'Test')
        self.assertListEqual(result, [{'test_key': 'test_value'}, {'test_key_2': 'test_value_2'}])


    def test_with_tokenized_method_empty_response(self):
        test_return = {
            'first_return': {
                'Test': []
            }
        }
        return_iter = iter(test_return)

        def fake_call(**kwargs):
            try:
                key = next(return_iter)
                return test_return[key]
            except StopIteration:
                return {}

        result = Aws.with_tokenized_method(fake_call, 'Test')
        self.assertListEqual(result, [])


    def test_with_tokenized_method_invalid_key(self):
        test_return = {
            'first_return': {
                'Test': [
                    {
                        'test_key': 'test_value'
                    }
                ]
            }
        }
        return_iter = iter(test_return)

        def fake_call(**kwargs):
            try:
                key = next(return_iter)
                return test_return[key]
            except StopIteration:
                return {}

        with self.assertRaises(AwsClientException):
            Aws.with_tokenized_method(fake_call, 'Unknow')
