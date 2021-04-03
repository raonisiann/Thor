import os

# thor must run from the project root
#
# Project root should have environment and
# image folders.
ROOT_DIR = os.getcwd()
BUILD_DIR = f'{ROOT_DIR}/build'
ENVIRONMENTS_DIR = f'{ROOT_DIR}/environments'
IMAGES_DIR = f'{ROOT_DIR}/images'
TEMPLATES_DIR = f'{ROOT_DIR}/templates'
