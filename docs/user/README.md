# Thor user documentation

## Project organization

## Environments folder
Environments should, idealy, maps to one AWS account and region (not a rule) and are represented by a folder under `$project_root/environments`.

## Images folder
Image basically maps directly to an AWS Machine Image (AMI). When the image is build `thor build` it produces an resulting AMI to be deployed later on. Images are represented by a folder under `$project_root/images`

### Compiling

Compilation process runs every time before `thor build` and `thor deploy` and generate build artifacs on `$project_root/build/$environment/$image` folder. Compilation provide support for templates based on Jinja2

### Variables file
The `variables.json` can be defined under image and environment (simultaneously) folders and store values in json format to be used on compilation proccess. Before compilatation files are processed and merged. Merging variables files have different behavior depending of its type. Strings values defined on image folder replace values defined in environment folder. List are concatenated. Dictionaries are merged recursively. If a dictionary has the same key with a string value defined in both image and environment, image wins. Variables defined under image folder always win any conflicts if existing.

### Template variables
The following variables can be retrieved from the tamplates during compiling.

- thor.env
- thor.image
- thor.build_dir
- var
  - Holds variables loaded from `variables.json`

### Processing order
Templates and files are processed in the following order:

- $image/templates
- $image/static
- $image/packer.json
- $image/config.json

The file structure is preserved on the build folder.

### Image config.json

Config file holds AWS Launch Template and AutoScaling information to be used during deployment. During the deployment, a new launch template and auto scaling group are created to deploy the image on AWS.

## Deployment proccess

### Overwiew
Deployment process initialize clients (boto3), and look for AWS credentials to create resources. By default, thor tries to load a credential profile that matches with the environment name, if fails, the normal boto3 credential chain is triggered. AWS Credential profile can be also overided on config.json with `aws_credential_profile` setting.

When initialization finishes, thor looks for the latest built image on AWS parameter store path `/thor/$env/$image/build/ami_id_list`. This is store an ordered list of 10 successful built images. The first (latest built) is retrieved. Then, thor check if there is any Auto Scaling groups running in the environment, if yes, it saves the current auto scaling capacity (Desired Capacity) and create a new one with settings defined in `config.json` under `scaling` and the current capacity. If not, the default capacity (1) is used. The launch template is created with settings defined under `launch_template` on `config.json` and the AMI retrieved before is used. Thor waits for desired capacity to available on Auto Scaling group before proceed to next step.

After new auto scaling is provisioned, thor starts the termination of the old running auto scaling group and ensure all instances are terminated before auto scaling group and launch template can be destroyed. Termination requests waits for traffic drain before it can be terminated at all, so depending on the load balancer or target group health checks it could take sometime to drain traffic from all instances.

On last step, thor updates the parameter store with the new running auto scaling group on `/thor/$env/$image/deploy/autoscaling_name`.
