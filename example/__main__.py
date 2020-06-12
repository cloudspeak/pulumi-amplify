"""
This example illustrates typical use of the AmplifyGraphQLAPI resource.  An Amplify
API called `notespulumi` has already been created using the Amplify CLI.  This example
creates a Cognito User Pool and then deploys a Pulumi-managed GraphQL API based on the
Amplify API which was generated.
"""

import pulumi
from pulumi_amplify import AmplifyGraphQLAPI
from pulumi_aws import cognito

user_pool = cognito.UserPool("NotesUserPool")

user_pool_client = cognito.UserPoolClient(
    "NotesUserPoolClient", user_pool_id=user_pool.id
)

graphql_api = AmplifyGraphQLAPI(
    "NotesAmplifyGraphQLAPI",
    amplify_api_name="notespulumi",
    graphql_types=["Note"],
    user_pool=user_pool,
    user_pool_client=user_pool_client,
    client_source_path="src",
)

pulumi.export("graphql_api_uri", graphql_api.graphql_api_uri)
