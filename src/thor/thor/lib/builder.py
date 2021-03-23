import os
import json
from datetime import datetime
from jinja2 import (
    Template,
    TemplateSyntaxError
)
from thor.lib.base import Base


class Builder(Base):

    def __init__(self, image):
        super().__init__()
        self.image = image
        self.build_number = int(datetime.now().timestamp())
        self.build_dir = '/tmp/thor/builds/{}'.format(self.build_number)
        self.artifacts_dir = '{}/artifacts'.format(self.build_dir)
        self.artifacts = []

    def build_dir(self):
        pass

    def load_json_file(self, path):
        if os.path.exists(path):
            with open(path) as f:
                return json.load(f)
        else:
            print('No %s variables file', path)
            return {}

    def get_artifacts(self):
        return self.artifacts

    def get_build_dir(self):
        return self.build_dir

    def get_build_number(self):
        return self.build_number

    def get_variables(self):
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
        return merged

    def get_thor_variables(self):
        return {
            'env': self.image.env.get_name(),
            'image': self.image.get_name(),
            'build_dir': self.get_build_dir(),
            'build_number': self.get_build_number()
        }

    def get_artifact_variables(self):
        return {
            'artifacts': self.get_artifacts()
        }

    def render_template(self, template):
        artifact_variables = self.get_artifact_variables()
        variables = self.get_variables()
        thor_variables = self.get_thor_variables()

        try:
            with open(template) as f:
                template = Template(f.read())
                try:
                    rendered = template.render(
                        artifact=artifact_variables,
                        thor=thor_variables,
                        var=variables,
                    )
                    return rendered
                except TemplateSyntaxError as err:
                    print(str(err))
        except OSError as err:
            print(str(err))
        exit(-1)

    def new_artifact(self, path, content):
        try:
            with open(path, 'w') as artifact:
                artifact.write(content)
                artifact_relative_name = path[len(self.artifacts_dir)+1:]
                self.artifacts.append(artifact_relative_name)
        except OSError as err:
            self.logger.error(str(err))
            exit(-1)

    def build_target_static(self):
        count = 0
        self.logger.info('Target "static" produced %s artifacts', count)

    def build_target_templates(self):
        source_files = self.image.get_template_files()
        count = 0

        for entry in source_files:
            basedir, subdirs, files = entry
            new_basedir = basedir[len(self.image.get_template_dir())+1:]

            if not new_basedir:
                new_basedir = '{}'.format(self.artifacts_dir)
            else:
                new_basedir = '{}/{}'.format(self.artifacts_dir,
                                             new_basedir)

            if not os.path.exists(new_basedir):
                try:
                    os.mkdir(new_basedir)
                except OSError as err:
                    self.logger.error(str(err))
                    exit(-1)

            for file_name in files:
                template = '{base_dir}/{file_name}'.format(
                    base_dir=basedir,
                    file_name=file_name
                )
                result = self.render_template(template)

                artifact_path = '{base_dir}/{file_name}'.format(
                    base_dir=new_basedir,
                    file_name=file_name
                )
                self.new_artifact(artifact_path, result)
                count += 1
        self.logger.info('Target "templates" produced %s artifacts', count)

    def build(self):
        if not os.path.exists(self.build_dir):
            try:
                os.makedirs(self.build_dir)
            except OSError as err:
                self.logger.error(str(err))
                exit(-1)

        self.build_target_static()
        self.build_target_templates()
