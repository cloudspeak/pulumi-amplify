from pathlib import Path
from re import match
from typing import List

import pulumi
from pulumi import ResourceOptions
from pulumi.output import Input, Output
from pulumi_aws import appsync, cognito, config, dynamodb, iam
from pulumi_aws.get_caller_identity import get_caller_identity

from .amplify_exports_file import AmplifyExportsFile
from .random_id import RandomId


class AmplifyGraphQLAPI(pulumi.ComponentResource):
    """
    This class represents an AWS Amplify-generated GraphQL API which is to be managed by
    Pulumi.
    """

    graphql_api_uri: Output[str]
    """
    The URI of the AppSync GraphQL API.
    """

    def __init__(
        self,
        name: str,
        amplify_api_name: Input[str],
        graphql_types: Input[List[str]],
        user_pool: Input[cognito.UserPool],
        user_pool_client: Input[cognito.UserPoolClient],
        client_source_path: Input[str] = "src",
        opts=None,
    ):
        """
        :param str name:                The Pulumi name for this resource
        :param str api_name:            The name of the API in Amplify
        :param List[str] graphql_types: The names of the GraphQL types, as defined in
                                        the schema, for which resolvers should be
                                        generated
        :param user_pool:               The Pulumi resource for the Cognito User Pool to
                                        be used for authenticating GraphQL requests
        :param user_pool_client:        The Pulumi resource for the Cognito User Pool
                                        client
        :param client_source_path:      The path to the client source directory.  This
                                        is where the `aws-exports.js` file will be
                                        placed.
        """
        super().__init__("nuage:aws:AmplifyGraphQLAPI", name, None, opts)

        self.amplify_api_name = amplify_api_name
        self.stack_name = amplify_api_name
        self.random_chars = RandomId.generate(8)
        self.amplify_api_build_dir = (
            Path("amplify/backend/api").joinpath(amplify_api_name).joinpath("build")
        )

        schema_path = self.amplify_api_build_dir.joinpath("schema.graphql")
        schema = schema_path.read_text()

        graphql_api = appsync.GraphQLApi(
            f"{self.stack_name}_graphql_api",
            authentication_type="AMAZON_COGNITO_USER_POOLS",
            user_pool_config={
                "default_action": "ALLOW",
                "user_pool_id": user_pool.id,
                "app_id_client_regex": user_pool_client.id,
            },
            schema=schema,
        )

        for type_name in graphql_types:
            resources = self.generate_dynamo_data_source(graphql_api, type_name)

        exports_file = AmplifyExportsFile(
            f"{self.stack_name}_exports_file",
            source_directory=client_source_path,
            parameters={
                "aws_project_region": config.region,
                "aws_cognito_region": config.region,
                "aws_user_pools_id": user_pool.id,
                "aws_user_pools_web_client_id": user_pool_client.id,
                "aws_appsync_graphqlEndpoint": graphql_api.uris["GRAPHQL"],
                "aws_appsync_region": config.region,
                "aws_appsync_authenticationType": "AMAZON_COGNITO_USER_POOLS",
            },
        )

        self.set_outputs({"graphql_api_uri": graphql_api.uris["GRAPHQL"]})

    def generate_dynamo_data_source(self, graphql_api, type_name):
        """
        Generates a DynamoDB data source for the given GraphQL type.  This includes the
        Dynamo table, the AppSync data source, a data source role, and the resolvers.

        NOTE: This function generates Dynamo tables with a hash key called `id`, but no
        other keys.

        :param type_name    The name of the GraphQL type.  This is the identifier which
                            appears after the `type` keyword in the schema.
        """

        table = dynamodb.Table(
            f"{self.stack_name}_{type_name}_table",
            name=f"{self.stack_name}_{self.random_chars}.{type_name}",
            hash_key="id",
            attributes=[{"name": "id", "type": "S"}],
            # stream_view_type="NEW_AND_OLD_IMAGES",
            billing_mode="PAY_PER_REQUEST",
        )

        data_source_iam_role = iam.Role(
            f"{self.stack_name}_{type_name}_role",
            assume_role_policy="""{
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {
                        "Service": "appsync.amazonaws.com"
                    },
                    "Action": "sts:AssumeRole"
                }
            ]
        }""",
        )

        aws_region = config.region
        account_id = get_caller_identity().account_id

        data_source_iam_role_policy = iam.RolePolicy(
            f"{self.stack_name}_{type_name}_role_policy",
            role=data_source_iam_role.name,
            name="MyDynamoDBAccess",
            policy=table.name.apply(
                lambda table_name: f"""{{
            "Version": "2012-10-17",
            "Statement": [
                {{
                    "Effect": "Allow",
                    "Action": [
                        "dynamodb:BatchGetItem",
                        "dynamodb:BatchWriteItem",
                        "dynamodb:PutItem",
                        "dynamodb:DeleteItem",
                        "dynamodb:GetItem",
                        "dynamodb:Scan",
                        "dynamodb:Query",
                        "dynamodb:UpdateItem"
                    ],
                    "Resource": [
                        "arn:aws:dynamodb:{aws_region}:{account_id}:table/{table_name}",
                        "arn:aws:dynamodb:{aws_region}:{account_id}:table/{table_name}/*"
                    ]
                }}
            ]
        }}"""
            ),
        )

        data_source = appsync.DataSource(
            f"{self.stack_name}_{type_name}_data_source",
            api_id=graphql_api.id,
            name=f"{type_name}TableDataSource_{self.random_chars}",
            type="AMAZON_DYNAMODB",
            service_role_arn=data_source_iam_role.arn,
            dynamodb_config={"table_name": table.name},
            opts=ResourceOptions(depends_on=[data_source_iam_role]),
        )

        resolvers = self.generate_resolvers(graphql_api, type_name, data_source)

        return {
            "table": table,
            "data_source_iam_role": data_source_iam_role,
            "data_source_iam_role_policy": data_source_iam_role_policy,
            "data_source": data_source,
            "resolvers": resolvers,
        }

    def generate_resolvers(self, graphql_api, type_name, data_source):
        """
        Creates AppSync resolvers for the given GraphQL type.  Resolvers are created by
        iterating through the `resolvers` directory in the API's build folder and
        parsing the resolver template filenames to find the operation name and type.

        :param type_name    The name of the GraphQL type.  This is the identifier which
                            appears after the `type` keyword in the schema.
        :param data_source  The AppSync data source Pulumi resource for the type.
        """
        resolvers_dir = self.amplify_api_build_dir.joinpath("resolvers")
        resolvers = []

        for req_file in resolvers_dir.iterdir():
            regex_match = match(
                f"^([a-zA-Z]+)\\.([a-zA-Z]+{type_name}s?)\\.req\\.vtl$",
                str(req_file.name),
            )

            if regex_match:
                operation_type = regex_match.group(1)
                operation_name = regex_match.group(2)
                res_file = resolvers_dir.joinpath(
                    f"{operation_type}.{operation_name}.res.vtl"
                )

                resolver = appsync.Resolver(
                    f"{self.stack_name}_{operation_name}_resolver",
                    api_id=graphql_api.id,
                    data_source=data_source.name,
                    field=operation_name,
                    type=operation_type,
                    request_template=req_file.read_text(),
                    response_template=res_file.read_text(),
                )

                resolvers.append(resolver)

        return resolvers

    def set_outputs(self, outputs: dict):
        """
        Adds the Pulumi outputs as attributes on the current object so they can be
        used as outputs by the caller, as well as registering them.
        """
        for output_name in outputs.keys():
            setattr(self, output_name, outputs[output_name])

        self.register_outputs(outputs)
