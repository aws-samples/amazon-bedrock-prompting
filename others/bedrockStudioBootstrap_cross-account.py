# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import json
import logging
import boto3
from botocore.exceptions import NoCredentialsError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
logger = logging.getLogger(__name__)

class BedrockStudioBootstrapper:
    def __init__(self, region="us-east-1", cross_account_role_arn=None):
        self._region = region
        self._cross_account_role_arn = cross_account_role_arn
        self._initialize_session()
        self._iam_client = self._session.client("iam")
        self._provisioning_role_name = "DataZoneBedrockProvisioningRole"
        self._service_role_name = "DataZoneBedrockServiceRole"
        self._permission_boundary_policy_name = "AmazonDataZoneBedrockPermissionsBoundary"

    def _initialize_session(self):
        logger.info("Initializing AWS session...")
        if self._cross_account_role_arn:
            sts_client = boto3.client('sts')
            assumed_role = sts_client.assume_role(
                RoleArn=self._cross_account_role_arn,
                RoleSessionName="BedrockStudioBootstrapSession"
            )
            credentials = assumed_role['Credentials']
            self._session = boto3.Session(
                aws_access_key_id=credentials['AccessKeyId'],
                aws_secret_access_key=credentials['SecretAccessKey'],
                aws_session_token=credentials['SessionToken'],
                region_name=self._region
            )
        else:
            self._session = boto3.Session(region_name=self._region)

        try:
            sts_client = self._session.client('sts')
            caller_identity = sts_client.get_caller_identity()
            self._account_id = caller_identity["Account"]
            self._current_principal_arn = caller_identity["Arn"]
            logger.info(f"Account ID: {self._account_id}")
            logger.info(f"AWS Region: {self._region}")
            logger.info(f"User/Role ARN: {self._current_principal_arn}")
        except NoCredentialsError:
            logger.error("No AWS credentials available. Please configure your credentials.")
            exit(1)

    def run(self):
        logger.info("=" * 80)
        logger.info("Running Bootstrapper for Bedrock Studio ...")
        self._create_provisioning_role()
        self._create_service_role()
        self._create_permission_boundary()
        logger.info("=" * 80)
        logger.info("All resources have been created.")

    def _create_role(self, role_name, trust_policy, role_policy):
        logger.info(f"Creating role: '{role_name}'...")
        try:
            response = self._iam_client.create_role(
                RoleName=role_name, AssumeRolePolicyDocument=trust_policy
            )
            role_arn = response["Role"]["Arn"]
            logger.info(f"Role created: {role_arn}")
        except self._iam_client.exceptions.EntityAlreadyExistsException:
            logger.warning(f"Role with name '{role_name}' already exists.")

        logger.info(f"Attaching inline policy to '{role_name}'...")
        try:
            self._iam_client.put_role_policy(
                RoleName=role_name,
                PolicyName="InlinePolicy",
                PolicyDocument=role_policy,
            )
            logger.info(f"Inline policy successfully attached.")
        except Exception as e:
            logger.error(f"Error attaching inline policy: {str(e)}")

    def _create_provisioning_role(self):
        logger.info("=" * 54)
        logger.info("Step 1: Create Provisioning Role.")
        logger.info("-" * 54)
        self._create_role(
            self._provisioning_role_name,
            self._get_provisioning_role_trust_policy(),
            self._get_provisioning_role_policy(),
        )

    def _create_service_role(self):
        logger.info("=" * 54)
        logger.info("Step 2: Create Service Role.")
        logger.info("-" * 54)
        self._create_role(
            self._service_role_name,
            self._get_service_role_trust_policy(),
            self._get_service_role_policy(),
        )

    def _create_permission_boundary(self):
        logger.info("=" * 80)
        logger.info("Step 3: Create Permission Boundary.")
        logger.info("-" * 80)
        logger.info(f"Creating permission boundary: '{self._permission_boundary_policy_name}'...")
        try:
            self._iam_client.create_policy(
                PolicyName=self._permission_boundary_policy_name,
                PolicyDocument=self._get_permission_boundary()
            )
            logger.info(f"Permission boundary policy created.")
        except self._iam_client.exceptions.EntityAlreadyExistsException:
            logger.warning(f"Policy with name '{self._permission_boundary_policy_name}' already exists.")

    def _get_provisioning_role_trust_policy(self):
        return json.dumps({
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Service": ["datazone.amazonaws.com"]},
                    "Action": ["sts:AssumeRole"],
                    "Condition": {"StringEquals": {"aws:SourceAccount": self._account_id}}
                }
            ]
        })

    def _get_service_role_trust_policy(self):
        return json.dumps({
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Service": ["datazone.amazonaws.com"]},
                    "Action": ["sts:AssumeRole", "sts:TagSession"],
                    "Condition": {
                        "StringEquals": {"aws:SourceAccount": self._account_id},
                        "ForAllValues:StringLike": {"aws:TagKeys": "datazone*"}
                    }
                }
            ]
        })

    def _get_provisioning_role_policy(self):
        account_id = self._account_id
        region = self._region
        return json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Sid": "AmazonDataZonePermissionsToCreateEnvironmentRole",
                        "Effect": "Allow",
                        "Action": [
                            "iam:CreateRole",
                            "iam:GetRolePolicy",
                            "iam:DetachRolePolicy",
                            "iam:AttachRolePolicy",
                            "iam:UpdateAssumeRolePolicy",
                        ],
                        "Resource": "arn:aws:iam::*:role/DataZoneBedrockProjectRole*",
                        "Condition": {
                            "StringEquals": {
                                "iam:PermissionsBoundary": f"arn:aws:iam::{account_id}:policy/{self._permission_boundary_policy_name}",
                                "aws:CalledViaFirst": ["cloudformation.amazonaws.com"],
                            },
                            "Null": {
                                "aws:ResourceTag/AmazonDataZoneEnvironment": "false"
                            },
                        },
                    },
                    {
                        "Sid": "AmazonDataZonePermissionsToServiceRole",
                        "Effect": "Allow",
                        "Action": [
                            "iam:CreateRole",
                            "iam:GetRolePolicy",
                            "iam:DetachRolePolicy",
                            "iam:AttachRolePolicy",
                            "iam:UpdateAssumeRolePolicy",
                        ],
                        "Resource": [
                            "arn:aws:iam::*:role/BedrockStudio*",
                            "arn:aws:iam::*:role/AmazonBedrockExecution*",
                        ],
                        "Condition": {
                            "StringEquals": {
                                "aws:CalledViaFirst": ["cloudformation.amazonaws.com"]
                            },
                            "Null": {
                                "aws:ResourceTag/AmazonDataZoneEnvironment": "false"
                            },
                        },
                    },
                    {
                        "Sid": "IamPassRolePermissionsForBedrock",
                        "Effect": "Allow",
                        "Action": ["iam:PassRole"],
                        "Resource": "arn:aws:iam::*:role/AmazonBedrockExecution*",
                        "Condition": {
                            "StringEquals": {
                                "iam:PassedToService": ["bedrock.amazonaws.com"],
                                "aws:CalledViaFirst": ["cloudformation.amazonaws.com"],
                            }
                        },
                    },
                    {
                        "Sid": "IamPassRolePermissionsForLambda",
                        "Effect": "Allow",
                        "Action": ["iam:PassRole"],
                        "Resource": ["arn:aws:iam::*:role/BedrockStudio*"],
                        "Condition": {
                            "StringEquals": {
                                "iam:PassedToService": ["lambda.amazonaws.com"],
                                "aws:CalledViaFirst": ["cloudformation.amazonaws.com"],
                            }
                        },
                    },
                    {
                        "Sid": "AmazonDataZonePermissionsToManageCreatedEnvironmentRole",
                        "Effect": "Allow",
                        "Action": [
                            "iam:DeleteRole",
                            "iam:GetRole",
                            "iam:DetachRolePolicy",
                            "iam:GetPolicy",
                            "iam:DeleteRolePolicy",
                            "iam:PutRolePolicy",
                        ],
                        "Resource": [
                            "arn:aws:iam::*:role/DataZoneBedrockProjectRole*",
                            "arn:aws:iam::*:role/AmazonBedrock*",
                            "arn:aws:iam::*:role/BedrockStudio*",
                        ],
                        "Condition": {
                            "StringEquals": {
                                "aws:CalledViaFirst": ["cloudformation.amazonaws.com"]
                            }
                        },
                    },
                    {
                        "Sid": "AmazonDataZoneCFStackCreationForEnvironments",
                        "Effect": "Allow",
                        "Action": [
                            "cloudformation:CreateStack",
                            "cloudformation:UpdateStack",
                            "cloudformation:TagResource",
                        ],
                        "Resource": ["arn:aws:cloudformation:*:*:stack/DataZone*"],
                        "Condition": {
                            "ForAnyValue:StringLike": {
                                "aws:TagKeys": "AmazonDataZoneEnvironment"
                            },
                            "Null": {
                                "aws:ResourceTag/AmazonDataZoneEnvironment": "false"
                            },
                        },
                    },
                    {
                        "Sid": "AmazonDataZoneCFStackManagementForEnvironments",
                        "Effect": "Allow",
                        "Action": [
                            "cloudformation:DeleteStack",
                            "cloudformation:DescribeStacks",
                            "cloudformation:DescribeStackEvents",
                        ],
                        "Resource": ["arn:aws:cloudformation:*:*:stack/DataZone*"],
                    },
                    {
                        "Sid": "AmazonDataZoneEnvironmentBedrockGetViaCloudformation",
                        "Effect": "Allow",
                        "Action": [
                            "bedrock:GetAgent",
                            "bedrock:GetAgentActionGroup",
                            "bedrock:GetAgentAlias",
                            "bedrock:GetAgentKnowledgeBase",
                            "bedrock:GetKnowledgeBase",
                            "bedrock:GetDataSource",
                            "bedrock:GetGuardrail",
                            "bedrock:DeleteGuardrail",
                        ],
                        "Resource": "*",
                        "Condition": {
                            "StringEquals": {
                                "aws:CalledViaFirst": ["cloudformation.amazonaws.com"]
                            }
                        },
                    },
                    {
                        "Sid": "AmazonDataZoneEnvironmentBedrockAgentPermissions",
                        "Effect": "Allow",
                        "Action": [
                            "bedrock:CreateAgent",
                            "bedrock:UpdateAgent",
                            "bedrock:DeleteAgent",
                            "bedrock:ListAgents",
                            "bedrock:CreateAgentActionGroup",
                            "bedrock:UpdateAgentActionGroup",
                            "bedrock:DeleteAgentActionGroup",
                            "bedrock:ListAgentActionGroups",
                            "bedrock:CreateAgentAlias",
                            "bedrock:UpdateAgentAlias",
                            "bedrock:DeleteAgentAlias",
                            "bedrock:ListAgentAliases",
                            "bedrock:AssociateAgentKnowledgeBase",
                            "bedrock:DisassociateAgentKnowledgeBase",
                            "bedrock:UpdateAgentKnowledgeBase",
                            "bedrock:ListAgentKnowledgeBases",
                            "bedrock:PrepareAgent",
                        ],
                        "Resource": "*",
                        "Condition": {
                            "StringEquals": {
                                "aws:CalledViaFirst": ["cloudformation.amazonaws.com"]
                            },
                            "Null": {"aws:ResourceTag/AmazonDataZoneProject": "false"},
                        },
                    },
                    {
                        "Sid": "AmazonDataZoneEnvironmentOpenSearch",
                        "Effect": "Allow",
                        "Action": [
                            "aoss:CreateAccessPolicy",
                            "aoss:DeleteAccessPolicy",
                            "aoss:UpdateAccessPolicy",
                            "aoss:GetAccessPolicy",
                            "aoss:ListAccessPolicies",
                            "aoss:CreateSecurityPolicy",
                            "aoss:DeleteSecurityPolicy",
                            "aoss:UpdateSecurityPolicy",
                            "aoss:GetSecurityPolicy",
                            "aoss:ListSecurityPolicies",
                        ],
                        "Resource": "*",
                        "Condition": {
                            "StringEquals": {
                                "aws:CalledViaFirst": ["cloudformation.amazonaws.com"]
                            }
                        },
                    },
                    {
                        "Sid": "AmazonDataZoneEnvironmentOpenSearchPermissions",
                        "Effect": "Allow",
                        "Action": [
                            "aoss:UpdateCollection",
                            "aoss:DeleteCollection",
                            "aoss:BatchGetCollection",
                            "aoss:ListCollections",
                            "aoss:CreateCollection",
                        ],
                        "Resource": "*",
                        "Condition": {
                            "StringEquals": {
                                "aws:CalledViaFirst": ["cloudformation.amazonaws.com"]
                            },
                            "Null": {"aws:ResourceTag/AmazonDataZoneProject": "false"},
                        },
                    },
                    {
                        "Sid": "AmazonDataZoneEnvironmentBedrockKnowledgeBasePermissions",
                        "Effect": "Allow",
                        "Action": [
                            "bedrock:CreateKnowledgeBase",
                            "bedrock:UpdateKnowledgeBase",
                            "bedrock:DeleteKnowledgeBase",
                            "bedrock:CreateDataSource",
                            "bedrock:UpdateDataSource",
                            "bedrock:DeleteDataSource",
                            "bedrock:ListKnowledgeBases",
                            "bedrock:ListDataSources",
                        ],
                        "Resource": "*",
                        "Condition": {
                            "StringEquals": {
                                "aws:CalledViaFirst": ["cloudformation.amazonaws.com"]
                            },
                            "Null": {"aws:ResourceTag/AmazonDataZoneProject": "false"},
                        },
                    },
                    {
                        "Sid": "AmazonDataZoneEnvironmentBedrockGuardrailPermissions",
                        "Effect": "Allow",
                        "Action": [
                            "bedrock:CreateGuardrail",
                            "bedrock:CreateGuardrailVersion",
                            "bedrock:DeleteGuardrail",
                            "bedrock:ListGuardrails",
                            "bedrock:ListTagsForResource",
                            "bedrock:TagResource",
                            "bedrock:UntagResource",
                            "bedrock:UpdateGuardrail",
                        ],
                        "Resource": "*",
                        "Condition": {
                            "StringEquals": {
                                "aws:CalledViaFirst": ["cloudformation.amazonaws.com"]
                            },
                            "Null": {"aws:ResourceTag/AmazonDataZoneProject": "false"},
                        },
                    },
                    {
                        "Sid": "AmazonDataZoneEnvironmentLambdaPermissions",
                        "Effect": "Allow",
                        "Action": [
                            "lambda:AddPermission",
                            "lambda:CreateFunction",
                            "lambda:ListFunctions",
                            "lambda:UpdateFunctionCode",
                            "lambda:UpdateFunctionConfiguration",
                            "lambda:InvokeFunction",
                            "lambda:ListVersionsByFunction",
                            "lambda:PublishVersion",
                        ],
                        "Resource": [
                            f"arn:aws:lambda:{region}:{account_id}:function:br-studio*",
                            f"arn:aws:lambda:{region}:{account_id}:function:OpensearchIndexLambda*",
                            f"arn:aws:lambda:{region}:{account_id}:function:IngestionTriggerLambda*",
                        ],
                        "Condition": {
                            "StringEquals": {
                                "aws:CalledViaFirst": ["cloudformation.amazonaws.com"]
                            },
                            "Null": {
                                "aws:ResourceTag/AmazonDataZoneEnvironment": "false"
                            },
                        },
                    },
                    {
                        "Sid": "AmazonDataZoneEnvironmentLambdaManagePermissions",
                        "Effect": "Allow",
                        "Action": [
                            "lambda:GetFunction",
                            "lambda:DeleteFunction",
                            "lambda:RemovePermission",
                        ],
                        "Resource": [
                            f"arn:aws:lambda:{region}:{account_id}:function:br-studio*",
                            f"arn:aws:lambda:{region}:{account_id}:function:OpensearchIndexLambda*",
                            f"arn:aws:lambda:{region}:{account_id}:function:IngestionTriggerLambda*",
                        ],
                        "Condition": {
                            "StringEquals": {
                                "aws:CalledViaFirst": ["cloudformation.amazonaws.com"]
                            }
                        },
                    },
                    {
                        "Sid": "ManageLogGroups",
                        "Effect": "Allow",
                        "Action": [
                            "logs:CreateLogGroup",
                            "logs:PutRetentionPolicy",
                            "logs:DeleteLogGroup",
                        ],
                        "Resource": [
                            "arn:aws:logs:*:*:log-group:/aws/lambda/br-studio-*",
                            "arn:aws:logs:*:*:log-group:datazone-*",
                        ],
                        "Condition": {
                            "StringEquals": {
                                "aws:CalledViaFirst": "cloudformation.amazonaws.com"
                            }
                        },
                    },
                    {
                        "Sid": "ListTags",
                        "Effect": "Allow",
                        "Action": [
                            "bedrock:ListTagsForResource",
                            "aoss:ListTagsForResource",
                            "lambda:ListTags",
                            "iam:ListRoleTags",
                            "iam:ListPolicyTags",
                        ],
                        "Resource": "*",
                        "Condition": {
                            "StringEquals": {
                                "aws:CalledViaFirst": "cloudformation.amazonaws.com"
                            }
                        },
                    },
                    {
                        "Sid": "AmazonDataZoneEnvironmentTagsCreationPermissions",
                        "Effect": "Allow",
                        "Action": [
                            "iam:TagRole",
                            "iam:TagPolicy",
                            "iam:UntagRole",
                            "iam:UntagPolicy",
                            "logs:TagLogGroup",
                            "bedrock:TagResource",
                            "bedrock:UntagResource",
                            "bedrock:ListTagsForResource",
                            "aoss:TagResource",
                            "aoss:UnTagResource",
                            "aoss:ListTagsForResource",
                            "lambda:TagResource",
                            "lambda:UnTagResource",
                            "lambda:ListTags",
                        ],
                        "Resource": "*",
                        "Condition": {
                            "ForAnyValue:StringLike": {
                                "aws:TagKeys": "AmazonDataZoneEnvironment"
                            },
                            "Null": {
                                "aws:ResourceTag/AmazonDataZoneEnvironment": "false"
                            },
                            "StringEquals": {
                                "aws:CalledViaFirst": ["cloudformation.amazonaws.com"]
                            },
                        },
                    },
                    {
                        "Sid": "AmazonDataZoneEnvironmentBedrockTagResource",
                        "Effect": "Allow",
                        "Action": ["bedrock:TagResource"],
                        "Resource": f"arn:aws:bedrock:{region}:{account_id}:agent-alias/*",
                        "Condition": {
                            "StringEquals": {
                                "aws:CalledViaFirst": ["cloudformation.amazonaws.com"]
                            },
                            "ForAnyValue:StringLike": {
                                "aws:TagKeys": "AmazonDataZoneEnvironment"
                            },
                        },
                    },
                    {
                        "Sid": "AmazonDataZoneEnvironmentKMSPermissions",
                        "Effect": "Allow",
                        "Action": [
                            "kms:GenerateDataKey",
                            "kms:Decrypt",
                            "kms:DescribeKey",
                            "kms:CreateGrant",
                            "kms:Encrypt",
                        ],
                        "Resource": "*",
                        "Condition": {
                            "StringEquals": {
                                "aws:ResourceTag/EnableBedrock": "true",
                                "aws:CalledViaFirst": ["cloudformation.amazonaws.com"],
                            }
                        },
                    },
                    {
                        "Sid": "PermissionsToGetAmazonDataZoneEnvironmentBlueprintTemplates",
                        "Effect": "Allow",
                        "Action": "s3:GetObject",
                        "Resource": "*",
                        "Condition": {
                            "StringEquals": {
                                "aws:CalledViaFirst": ["cloudformation.amazonaws.com"]
                            },
                            "StringNotEquals": {
                                "aws:ResourceAccount": "${aws:PrincipalAccount}"
                            },
                        },
                    },
                    {
                        "Sid": "PermissionsToManageSecrets",
                        "Effect": "Allow",
                        "Action": ["secretsmanager:GetRandomPassword"],
                        "Resource": "*",
                        "Condition": {
                            "StringEquals": {
                                "aws:CalledViaFirst": ["cloudformation.amazonaws.com"]
                            }
                        },
                    },
                    {
                        "Sid": "PermissionsToStoreSecrets",
                        "Effect": "Allow",
                        "Action": [
                            "secretsmanager:CreateSecret",
                            "secretsmanager:TagResource",
                            "secretsmanager:UntagResource",
                            "secretsmanager:PutResourcePolicy",
                            "secretsmanager:DeleteResourcePolicy",
                            "secretsmanager:DeleteSecret",
                        ],
                        "Resource": "*",
                        "Condition": {
                            "StringEquals": {
                                "aws:CalledViaFirst": ["cloudformation.amazonaws.com"]
                            },
                            "Null": {
                                "aws:ResourceTag/AmazonDataZoneEnvironment": "false"
                            },
                        },
                    },
                    {
                        "Sid": "AmazonDataZoneManageProjectBuckets",
                        "Effect": "Allow",
                        "Action": [
                            "s3:CreateBucket",
                            "s3:DeleteBucket",
                            "s3:PutBucketTagging",
                            "s3:PutEncryptionConfiguration",
                            "s3:PutBucketVersioning",
                            "s3:PutBucketCORS",
                            "s3:PutBucketPublicAccessBlock",
                            "s3:PutBucketPolicy",
                            "s3:PutLifecycleConfiguration",
                            "s3:DeleteBucketPolicy",
                        ],
                        "Resource": "arn:aws:s3:::br-studio-*",
                        "Condition": {
                            "StringEquals": {
                                "aws:CalledViaFirst": ["cloudformation.amazonaws.com"]
                            }
                        },
                    },
                    {
                        "Sid": "CreateServiceLinkedRoleForOpenSearchServerless",
                        "Effect": "Allow",
                        "Action": "iam:CreateServiceLinkedRole",
                        "Resource": "*",
                        "Condition": {
                            "StringEquals": {
                                "iam:AWSServiceName": "observability.aoss.amazonaws.com",
                                "aws:CalledViaFirst": "cloudformation.amazonaws.com",
                            }
                        },
                    },
                ],
            }
        )
        pass

    def _get_service_role_policy(self):
        return json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Sid": "DomainExecutionRoleStatement",
                        "Effect": "Allow",
                        "Action": [
                            "datazone:GetDomain",
                            "datazone:ListProjects",
                            "datazone:GetProject",
                            "datazone:CreateProject",
                            "datazone:UpdateProject",
                            "datazone:DeleteProject",
                            "datazone:ListProjectMemberships",
                            "datazone:CreateProjectMembership",
                            "datazone:DeleteProjectMembership",
                            "datazone:ListEnvironments",
                            "datazone:GetEnvironment",
                            "datazone:CreateEnvironment",
                            "datazone:UpdateEnvironment",
                            "datazone:DeleteEnvironment",
                            "datazone:ListEnvironmentBlueprints",
                            "datazone:GetEnvironmentBlueprint",
                            "datazone:CreateEnvironmentBlueprint",
                            "datazone:UpdateEnvironmentBlueprint",
                            "datazone:DeleteEnvironmentBlueprint",
                            "datazone:ListEnvironmentBlueprintConfigurations",
                            "datazone:ListEnvironmentBlueprintConfigurationSummaries",
                            "datazone:ListEnvironmentProfiles",
                            "datazone:GetEnvironmentProfile",
                            "datazone:CreateEnvironmentProfile",
                            "datazone:UpdateEnvironmentProfile",
                            "datazone:DeleteEnvironmentProfile",
                            "datazone:UpdateEnvironmentDeploymentStatus",
                            "datazone:GetEnvironmentCredentials",
                            "datazone:ListGroupsForUser",
                            "datazone:SearchUserProfiles",
                            "datazone:SearchGroupProfiles",
                            "datazone:GetUserProfile",
                            "datazone:GetGroupProfile",
                        ],
                        "Resource": "*",
                    },
                    {
                        "Sid": "RAMResourceShareStatement",
                        "Effect": "Allow",
                        "Action": "ram:GetResourceShareAssociations",
                        "Resource": "*",
                    },
                    {
                        "Effect": "Allow",
                        "Action": [
                            "bedrock:InvokeModel",
                            "bedrock:InvokeModelWithResponseStream",
                            "bedrock:GetFoundationModelAvailability",
                        ],
                        "Resource": "*",
                    },
                    {
                        "Effect": "Allow",
                        "Action": [
                            "kms:DescribeKey",
                            "kms:GenerateDataKey",
                            "kms:Decrypt",
                        ],
                        "Resource": "*",
                    },
                ],
            }
        )
        pass

    def _get_permission_boundary(self):
        return json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Sid": "BedrockEnvironmentRoleKMSDecryptPermissions",
                        "Effect": "Allow",
                        "Action": ["kms:Decrypt", "kms:GenerateDataKey"],
                        "Resource": "*",
                        "Condition": {
                            "StringEquals": {"aws:ResourceTag/EnableBedrock": "true"}
                        },
                    },
                    {
                        "Sid": "BedrockRuntimeAgentPermissions",
                        "Effect": "Allow",
                        "Action": ["bedrock:InvokeAgent"],
                        "Resource": "*",
                        "Condition": {
                            "Null": {"aws:ResourceTag/AmazonDataZoneProject": "false"}
                        },
                    },
                    {
                        "Sid": "BedrockRuntimeModelsAndJobsRole",
                        "Effect": "Allow",
                        "Action": [
                            "bedrock:InvokeModel",
                            "bedrock:InvokeModelWithResponseStream",
                            "bedrock:RetrieveAndGenerate",
                        ],
                        "Resource": "*",
                    },
                    {
                        "Sid": "BedrockApplyGuardrails",
                        "Effect": "Allow",
                        "Action": ["bedrock:ApplyGuardrail"],
                        "Resource": "*",
                        "Condition": {
                            "Null": {"aws:ResourceTag/AmazonDataZoneProject": "false"}
                        },
                    },
                    {
                        "Sid": "BedrockRuntimePermissions",
                        "Effect": "Allow",
                        "Action": [
                            "bedrock:Retrieve",
                            "bedrock:StartIngestionJob",
                            "bedrock:GetIngestionJob",
                            "bedrock:ListIngestionJobs",
                        ],
                        "Resource": "*",
                        "Condition": {
                            "Null": {"aws:ResourceTag/AmazonDataZoneProject": "false"}
                        },
                    },
                    {
                        "Sid": "BedrockFunctionsPermissions",
                        "Action": ["secretsmanager:PutSecretValue"],
                        "Resource": "arn:aws:secretsmanager:*:*:secret:br-studio/*",
                        "Effect": "Allow",
                        "Condition": {
                            "Null": {"aws:ResourceTag/AmazonDataZoneProject": "false"}
                        },
                    },
                    {
                        "Sid": "BedrockS3ObjectsHandlingPermissions",
                        "Action": [
                            "s3:GetObject",
                            "s3:PutObject",
                            "s3:GetObjectVersion",
                            "s3:ListBucketVersions",
                            "s3:DeleteObject",
                            "s3:DeleteObjectVersion",
                            "s3:ListBucket",
                        ],
                        "Resource": [f"arn:aws:s3:::br-studio-{self._account_id}-*"],
                        "Effect": "Allow",
                    },
                ],
            }
        )
        pass

def main():
    region = "us-east-1"  # Change this to your desired region
    cross_account_role_arn = "arn:aws:iam::TARGET_ACCOUNT_ID:role/BedrockStudioCrossAccountRole"  # Replace TARGET_ACCOUNT_ID with the actual account ID

    bootstrapper = BedrockStudioBootstrapper(region=region, cross_account_role_arn=cross_account_role_arn)
    bootstrapper.run()

if __name__ == "__main__":
    main()