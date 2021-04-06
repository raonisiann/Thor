import os
import json

from datetime import datetime
from jinja2 import (
    Environment,
    FileSystemLoader,
    Template,
    TemplateSyntaxError,
    UndefinedError
)
from thor.lib.base import Base
from thor.lib.config import Config
from thor.lib.thor import Thor
from thor.lib.utils.names_generator import random_string
from thor.lib.aws_resources.parameter_store import (
    ParameterStore,
    ParameterStoreNotFoundException
)


class CompilerArtifactGenerationException(Exception):
    pass


class CompilerTemplateRenderingException(Exception):
    pass


class CompilerException(Exception):
    pass


class Compiler(Base):

    def __init__(self, image):
        super().__init__()
        self.image = image
        self.build_targets = [
            {'name': 'clean', 'func': self.build_target_clean},
            {'name': 'static', 'func': self.build_target_static},
            {'name': 'templates', 'func': self.build_target_templates},
            {'name': 'packer', 'func': self.build_target_packer},
            {'name': 'config', 'func': self.build_target_config}
        ]
        self.build_dir = '{base_build_dir}/{env_name}/{image_name}'.format(
            base_build_dir=Thor.BUILD_DIR,
            env_name=image.env.get_name(),
            image_name=image.get_name()
        )
        # compiler overrides default config file localtion
        # to use the one after build process.
        self.image.config = Config(f'{self.build_dir}/config.json')
        self.build_info_file = f'{self.build_dir}/build_info.json'
        self.start_time = ''
        self.end_time = ''
        self.artifacts = []
        self.random_string = random_string()
        self.variables = None
        self.is_build_dir_created = False
        self.__saved_dir = None

    def __create_build_dirs(self):
        if not self.is_build_dir_created:
            if not os.path.exists(self.build_dir):
                self.logger.info(f'Creating dir {self.build_dir}')
                try:
                    os.makedirs(self.build_dir)
                    self.is_build_dir_created = True
                except OSError as err:
                    self.logger.error(f'Fail to create dir {self.build_dir}')
                    raise CompilerException(str(err))

    def __cd(self, path):
        try:
            self.logger.info(f'cd {path}')
            os.chdir(path)
        except OSError as err:
            self.logger.error(f'Fail to cd into {path}')
            raise CompilerException(str(err))

    def __enter__(self):
        self.__create_build_dirs()
        self.__saved_dir = os.getcwd()
        self.__cd(self.build_dir)
        return self

    def __exit__(self, type, value, traceback):
        self.__cd(self.__saved_dir)
        self.__saved_dir = None

    def load_json_file(self, path):
        if os.path.exists(path):
            self.logger.info(f'Loading variables file {path}')
            with open(path) as f:
                return json.load(f)
        else:
            return {}

    def get_artifacts(self):
        return self.artifacts

    def get_build_dir(self):
        return self.build_dir

    def get_build_info_file(self):
        return self.build_info_file

    def get_variables(self):
        if self.variables is None:
            env_vars = self.load_json_file(self.image.env.get_variables_file())
            img_vars = self.load_json_file(self.image.get_variables_file())
            merged = dict(env_vars)

            for k, v in img_vars.items():
                if k in merged:
                    if type(v) is dict:
                        merged[k] = {**merged[k], **v}
                    elif type(v) is list:
                        merged[k] = merged[k] + v
                    else:
                        merged[k] = v
                else:
                    merged[k] = v
            self.variables = merged
        return self.variables

    def get_thor_variables(self):
        return {
            'env': self.image.env.get_name(),
            'image': self.image.get_name(),
            'build_dir': self.get_build_dir(),
            'random_string': self.random_string
        }

    def get_artifact_variables(self):
        return {
            'files': self.get_artifacts()
        }

    def generate_template_variables(self):
        return {
            'artifacts': self.get_artifacts(),
            'thor': self.get_thor_variables(),
            'var': self.get_variables()
        }

    def generate_build_info_file(self):
        self.logger.info('Generating build info file..')
        build_info = {
            'start_time': str(self.start_time),
            'end_time': str(self.end_time),
            'variables': self.generate_template_variables()
        }
        with open(self.build_info_file, 'w') as f:
            json.dump(build_info, f, indent=4)
        self.logger.info(f'Build info file => {self.build_info_file}')

    def abort_build(self, reason):
        self.logger.error(reason)
        self.logger.info('Aborting...')
        exit(-1)

    def build_target_static(self):
        self.logger.info('Building target => static...')
        self.__create_build_dirs()
        static_files = self.image.get_static_files()
        dest_dir = f'{self.build_dir}/static'
        count = 0

        if len(static_files) == 0:
            self.logger.info('No static files to build')

        for entry in static_files:
            base_dir, sub_dirs, files = entry
            new_base_dir = base_dir[len(self.image.get_static_dir())+1:]

            if not new_base_dir:
                new_base_dir = f'{dest_dir}'
            else:
                new_base_dir = f'{dest_dir}/{new_base_dir}'

            if not os.path.exists(new_base_dir):
                try:
                    self.logger.info(f'Creating dir {new_base_dir}')
                    os.makedirs(new_base_dir, exist_ok=True)
                except OSError as err:
                    self.abort_build(str(err))
            # copy static files
            for file_name in files:
                static_file_name = f'{base_dir}/{file_name}'
                try:
                    self.logger.info(f'Copying {static_file_name}')
                    with open(static_file_name, 'rb') as src:
                        content = src.read()
                        dst_file_name = f'{new_base_dir}/{file_name}'
                        self.logger.info(f'destination => {dst_file_name}')
                        with open(dst_file_name, 'wb') as dst:
                            dst.write(content)
                    self.logger.info('File copy completed with success')
                    count += 1
                    self.logger.info('Build completed')
                    self.logger.info(f'Target => static, Artifacts => {count}')
                except OSError as err:
                    self.logger.error('Fail to copy static file')
                    self.abort_build(str(err))
        return 'success'

    def build_target_templates(self):
        self.logger.info('Building target => templates...')
        self.__create_build_dirs()
        # Last in the list replaces top ones.
        # This is ordered to resolves conflits, if any.
        #
        # 1. global templates
        # 2. environment templates
        # 3. image templates
        template_list = [
            self.image.get_template_dir(),
            self.image.env.get_template_dir(),
            Thor.TEMPLATES_DIR,
        ]
        dest_dir = f'{self.build_dir}/templates'
        template = CompilerTemplateDir(self.image, dest_dir, template_list)
        try:
            count = template.render_all(self.generate_template_variables())
            self.logger.info('Build completed')
            self.logger.info(f'Target => templates, Artifacts => {count}')
            return 'success'
        except CompilerTemplateRenderingException as err:
            self.abort_build(str(err))

    def build_target_packer(self):
        self.logger.info('Building target => packer...')
        self.__create_build_dirs()
        packer_file = self.image.get_packer_file()
        if packer_file:
            with open(packer_file, 'r') as f:
                packer_file_content = f.read()
            try:
                template = CompilerTemplateString(self.image, self.build_dir,
                                                  packer_file_content)
                template.render('packer.json',
                                self.generate_template_variables())
                self.logger.info('Build completed')
                self.logger.info('Target => packer, Artifacts => 1')
            except CompilerArtifactGenerationException as err:
                self.abort_build(str(err))
        else:
            self.logger.info('No packer file to compile')
            self.logger.info('Target => packer, Artifacts => 0')
        return 'success'

    def build_target_config(self):
        self.logger.info('Building target => config...')
        self.__create_build_dirs()
        env_config = {}
        image_config = {}

        if os.path.exists(self.image.env.get_config_file()):
            with open(self.image.env.get_config_file(), 'r') as f:
                env_config = json.loads(f.read())

        if os.path.exists(self.image.get_config_file()):
            with open(self.image.get_config_file(), 'r') as f:
                image_config = json.loads(f.read())
        # image settings override environment settings
        merged_config = json.dumps({**env_config, **image_config}, indent=4)

        try:
            self.logger.info('Loading merged config')
            try:
                self.logger.info('Rendering...')
                template = CompilerTemplateString(self.image, self.build_dir,
                                                  merged_config)
                template.render('config.json',
                                self.generate_template_variables())
                self.logger.info('Rendering Done!')
                self.logger.info('Build completed')
                self.logger.info('Target => config, Artifacts => 1')
                return 'success'
            except TemplateSyntaxError as err:
                CompilerTemplateRenderingException(str(err))
        except OSError as err:
            CompilerTemplateRenderingException(str(err))

    def build_all(self):
        self.start_time = datetime.now()
        for target_item in self.build_targets:
            target = target_item['func']
            result = target()
            if not result == 'success':
                # force the proccess to terminate if we not get
                # success from target.
                return 'fail'
        self.end_time = datetime.now()
        self.generate_build_info_file()
        return 'success'

    def __remove_dirs_recursive(self, path):
        if os.path.exists(path):
            entries = os.scandir(path=path)
            for entry in entries:
                entry_path = f'{path}/{entry.name}'

                try:
                    if entry.is_dir():
                        self.__remove_dirs_recursive(f'{entry_path}')
                        self.logger.info(f'Removing dir {entry_path}')
                        os.rmdir(entry_path)
                    else:
                        self.logger.info(f'Removing file {entry_path}')
                        os.remove(entry_path)
                except OSError as err:
                    self.logger.error(f'Fail to remove {entry_path}')
                    raise CompilerException(str(err))

    def build_target_clean(self):
        self.logger.info(f'Cleaning {self.build_dir}')
        self.__remove_dirs_recursive(self.build_dir)
        self.logger.info('Clean done!')
        return 'success'

    def build(self):
        self.build_all()
        self.logger.info(f'Build dir ==> {self.build_dir}')
        self.logger.info('Build completed with success!')
        return 'success'


class CompilerTemplate(Base):

    def __init__(self, image, dst_dir, jinja_env):
        super().__init__()
        self.image = image
        self.dst_dir = dst_dir
        self.jinja_env = jinja_env
        self.jinja_env.filters['getparam'] = self.filter_get_param

    def filter_get_param(self, name):
        env_name = self.image.env.get_name()
        image_name = self.image.get_name()
        param_full_name = f'/thor/{env_name}/{image_name}/{name}'
        param = ParameterStore(self.image.env)

        try:
            return param.get(param_full_name)
        except ParameterStoreNotFoundException:
            error_msg = f'Parameter {param_full_name} not found'
            raise UndefinedError(error_msg)


class CompilerTemplateString(CompilerTemplate):

    def __init__(self, image, dst_dir, template_string):
        super().__init__(image, dst_dir, Environment())
        self.template_string = template_string

    def render(self, dst_file, variables):
        self.logger.info(f'Rendering {dst_file}')
        rendered = self.jinja_env.from_string(self.template_string)
        stream = rendered.stream(variables)
        template_dst_path = f'{self.dst_dir}/{dst_file}'
        template_dst_dir = os.path.dirname(template_dst_path)

        try:
            os.makedirs(template_dst_dir, exist_ok=True)
            # remove template extension if exists
            if '.tmpl' == template_dst_path[-5:]:
                template_dst_path = template_dst_path[:-5]
            stream.dump(template_dst_path)
            self.logger.info('Rendering completed')
        except TemplateSyntaxError as err:
            raise CompilerTemplateRenderingException(str(err))
        except UndefinedError as err:
            raise CompilerTemplateRenderingException(str(err))
        except OSError as err:
            raise CompilerTemplateRenderingException(str(err))


class CompilerTemplateDir(CompilerTemplate):

    def __init__(self, image, dst_dir, templates_dir):
        super().__init__(
            image,
            dst_dir,
            Environment(loader=FileSystemLoader(templates_dir)))

    def render(self, template, variables):
        self.logger.info(f'Rendering {template}')
        stream = self.jinja_env.get_template(template).stream(variables)
        template_dst_path = f'{self.dst_dir}/{template}'
        template_dst_dir = os.path.dirname(template_dst_path)

        try:
            os.makedirs(template_dst_dir, exist_ok=True)
            # remove template extension if exists
            if '.tmpl' == template_dst_path[-5:]:
                template_dst_path = template_dst_path[:-5]
            stream.dump(template_dst_path)
            self.logger.info('Rendering completed')
        except TemplateSyntaxError as err:
            raise CompilerTemplateRenderingException(str(err))
        except UndefinedError as err:
            raise CompilerTemplateRenderingException(str(err))
        except OSError as err:
            raise CompilerTemplateRenderingException(str(err))

    def render_all(self, variables):
        count = 0
        for template in self.jinja_env.list_templates():
            self.render(template, variables)
            count += 1
        return count
