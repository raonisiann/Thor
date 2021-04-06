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
        self.build_targets = {
            'static': self.build_target_static,
            'packer': self.build_target_packer,
            'templates': self.build_target_templates
        }
        self.build_dir = '{base_build_dir}/{env_name}/{image_name}'.format(
            base_build_dir=Thor.BUILD_DIR,
            env_name=image.env.get_name(),
            image_name=image.get_name()
        )
        self.build_info_file = f'{self.build_dir}/build_info.json'
        self.start_time = ''
        self.end_time = ''
        self.artifacts = []
        self.random_string = random_string()
        self.variables = None
        self.__saved_dir = None

    def __create_build_dirs(self):
        if not os.path.exists(self.build_dir):
            self.logger.info(f'Creating dir {self.build_dir}')
            try:
                os.makedirs(self.build_dir)
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

    def render_template(self, template_path):
        try:
            self.logger.info(f'Loading template {template_path}')
            with open(template_path) as f:
                template = Template(f.read())
                try:
                    self.logger.info('Rendering...')
                    rendered = template.render(
                        **self.generate_template_variables())
                    self.logger.info('Rendering Done!')
                    return rendered
                except TemplateSyntaxError as err:
                    CompilerTemplateRenderingException(str(err))
        except OSError as err:
            CompilerTemplateRenderingException(str(err))

    def new_artifact(self, path, content):
        try:
            # remove template extesion if existing
            if '.tmpl' == path[-5:]:
                artifact_file = path[:-5]
            else:
                artifact_file = path
            artifact_relative_name = artifact_file[len(self.build_dir)+1:]
            self.logger.info(f'Creating artifact => {artifact_relative_name}')

            with open(artifact_file, 'w') as artifact:
                artifact.write(content)
                self.artifacts.append(artifact_relative_name)
                self.logger.info('Artifact generated')
        except OSError as err:
            self.logger.error('Fail to generated artifact {path}')
            raise CompilerArtifactGenerationException(str(err))

    def abort_build(self, reason):
        self.logger.error(reason)
        self.logger.info('Aborting...')
        exit(-1)

    def build_target_static(self):
        static_files = self.image.get_static_files()
        dest_dir = f'{self.build_dir}/static'
        count = 0

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
                except OSError as err:
                    self.logger.error('Fail to copy static file')
                    self.abort_build(str(err))
        return count

    def build_target_templates(self):
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
        template = CompilerTemplate(self.image, template_list, dest_dir)
        try:
            return template.render_all(self.generate_template_variables())
        except CompilerTemplateRenderingException as err:
            self.abort_build(str(err))

    def build_target_packer(self):
        count = 0
        packer_file = self.image.get_packer_file()
        if packer_file:

            try:
                dst_packer_file = f'{self.build_dir}/packer.json'
                result = self.render_template(packer_file)
                self.new_artifact(dst_packer_file, result)
                count += 1
            except CompilerArtifactGenerationException as err:
                self.abort_build(str(err))

        return count

    def build_all(self):
        self.start_time = datetime.now()
        for name, target in self.build_targets.items():
            self.logger.info(f'Building target => {name}...')
            result = target()
            self.logger.info('Build completed')
            self.logger.info(f'Target => {name}, Artifacts => {result}')
        self.end_time = datetime.now()
        self.generate_build_info_file()

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

    def clean_build_dir(self):
        self.logger.info(f'Cleaning {self.build_dir}')
        self.__remove_dirs_recursive(self.build_dir)

    def build(self):
        self.clean_build_dir()
        self.__create_build_dirs()
        self.build_all()
        self.logger.info(f'Build dir ==> {self.build_dir}')
        self.logger.info('Build completed with success!')


class CompilerTemplate(Base):

    def __init__(self, image, templates_dir, dst_dir):
        super().__init__()
        self.image = image
        self.dst_dir = dst_dir
        self.jinja_env = Environment(loader=FileSystemLoader(templates_dir))
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
