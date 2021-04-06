import os


class Thor:
    # Project root dir
    ROOT_DIR = os.getcwd()
    # Main build directory
    BUILD_DIR = f'{ROOT_DIR}/build'
    # Environments folder
    ENVIRONMENTS_DIR = f'{ROOT_DIR}/environments'
    # Images directory
    IMAGES_DIR = f'{ROOT_DIR}/images'
    # Global static files directory
    STATIC_DIR = f'{ROOT_DIR}/static'
    # Global templates directory
    TEMPLATES_DIR = f'{ROOT_DIR}/templates'

    @classmethod
    def get_template_files(cls):
        if os.path.exists(cls.TEMPLATES_DIR):
            return list(os.walk(cls.TEMPLATES_DIR))
        else:
            return []

    @classmethod
    def get_static_files(cls):
        if os.path.exists(cls.STATIC_DIR):
            return list(os.walk(cls.STATIC_DIR))
        else:
            return []
