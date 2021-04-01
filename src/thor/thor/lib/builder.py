import os
import json

from thor.lib import thor
from jinja2 import (
    Template,
    TemplateSyntaxError
)
from thor.lib.base import Base


class BuilderArtifactGenerationException(Exception):
    pass


class BuilderTemplateRenderingException(Exception):
    pass


class BuilderException(Exception):
    pass


class Builder(Base):

    def __init__(self, image):
        super().__init__()
        self.image = image
        self.build_targets = {
            'static': self.build_target_static,
            'templates': self.build_target_templates
        }
        self.build_dir = '{project_dir}/build/{env_name}/{image_name}'.format(
            project_dir=thor.ROOT_DIR,
            env_name=image.env.get_name(),
            image_name=image.get_name()
        )
        self.artifacts = []
        self.variables = None
        self.__saved_dir = None

    def __create_build_dirs(self):
        if not os.path.exists(self.build_dir):
            self.logger.info(f'Creating dir {self.build_dir}')
            try:
                os.makedirs(self.build_dir)
            except OSError as err:
                self.logger.error(f'Fail to create dir {self.build_dir}')
                raise BuilderException(str(err))

    def __cd(self, path):
        try:
            self.logger.info(f'cd {path}')
            os.chdir(path)
        except OSError as err:
            self.logger.error(f'Fail to cd into {path}')
            raise BuilderException(str(err))

    def __enter__(self):
        self.__create_build_dirs()
        self.__saved_dir = os.getcwd()
        self.__cd(self.build_dir)

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
            'build_dir': self.get_build_dir()
        }

    def get_artifact_variables(self):
        return {
            'artifacts': self.get_artifacts()
        }

    def render_template(self, template_path):
        artifact_variables = self.get_artifact_variables()
        variables = self.get_variables()
        thor_variables = self.get_thor_variables()

        try:
            self.logger.info(f'Loading template {template_path}')
            with open(template_path) as f:
                template = Template(f.read())
                try:
                    self.logger.info('Rendering...')
                    rendered = template.render(
                        artifact=artifact_variables,
                        thor=thor_variables,
                        var=variables,
                    )
                    self.logger.info('Rendering Done!')
                    return rendered
                except TemplateSyntaxError as err:
                    BuilderTemplateRenderingException(str(err))
        except OSError as err:
            BuilderTemplateRenderingException(str(err))

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
            raise BuilderArtifactGenerationException(str(err))

    def abort_build(self, reason):
        self.logger.error(reason)
        self.logger.info('Aborting...')
        exit(-1)

    def build_target_static(self):
        return 0

    def build_target_templates(self):
        source_files = self.image.get_template_files()
        dest_dir = f'{self.build_dir}/templates'
        count = 0

        for entry in source_files:
            base_dir, sub_dirs, files = entry
            new_base_dir = base_dir[len(self.image.get_template_dir())+1:]

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

            for file_name in files:
                template = f'{base_dir}/{file_name}'

                try:
                    result = self.render_template(template)
                except BuilderTemplateRenderingException as err:
                    self.abort_build(str(err))

                artifact_path = f'{new_base_dir}/{file_name}'

                try:
                    self.new_artifact(artifact_path, result)
                    count += 1
                except BuilderArtifactGenerationException as err:
                    self.abort_build(str(err))
        return count

    def build_all(self):
        for name, target in self.build_targets.items():
            self.logger.info(f'Building target => {name}...')
            result = target()
            self.logger.info('Build completed')
            self.logger.info(f'Target => {name}, Artifacts => {result}')

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
                    raise BuilderException(str(err))

    def clean_build_dir(self):
        self.logger.info(f'Cleaning {self.build_dir}')
        self.__remove_dirs_recursive(self.build_dir)

    def build(self):
        self.clean_build_dir()
        self.__create_build_dirs()
        self.build_all()
        self.logger.info(f'Build dir ==> {self.build_dir}')
        self.logger.info('Build completed with success!')
