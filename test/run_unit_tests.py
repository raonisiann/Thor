from unittest import TestLoader, TextTestRunner


def get_tests():
    loader = TestLoader()
    return loader.discover('./thor/', 'test_*.py')


if __name__ == '__main__':
    runner = TextTestRunner(verbosity=2)
    runner.run(get_tests())
