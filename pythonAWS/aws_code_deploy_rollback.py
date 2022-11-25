import datetime

import boto3

client = boto3.client('codedeploy')
applicationName = 'hackathon'
s3Bucket = 's3-deployment'
s3KeyPrefix = 'hackathon'

response = client.list_application_revisions(
    applicationName=applicationName,
    sortBy='lastUsedTime',
    sortOrder='descending',
    s3Bucket=s3Bucket,
    s3KeyPrefix=s3KeyPrefix)

latestKey = response['revisions'][0]['s3Location']['key']
latestETag = response['revisions'][0]['s3Location']['eTag']
response = client.get_application_revision(
    applicationName='hackathon',
    revision={
        'revisionType': 'S3',
        's3Location': {
            'bucket': s3Bucket,
            'key': latestKey,
            'bundleType': 'zip',
            'eTag': latestETag
        }
    }
)

last_deployment_time = response['revisionInfo']['lastUsedTime'].replace(tzinfo=None)
fifteen_minutes_ago = datetime.datetime.now() - datetime.timedelta(minutes=15)

if last_deployment_time > fifteen_minutes_ago:
    print("Last Deployment was done within 15 minutes ago")

    print("Fetching the previous deployment revision")
    response = client.list_application_revisions(
        applicationName=applicationName,
        sortBy='lastUsedTime',
        sortOrder='descending',
        s3Bucket=s3Bucket,
        s3KeyPrefix=s3KeyPrefix)

    previousKey = response['revisions'][1]['s3Location']['key']
    previousETag = response['revisions'][1]['s3Location']['eTag']

    print("Rollback to previous version")
    response = client.create_deployment(
        applicationName=applicationName,
        deploymentGroupName=applicationName,
        revision={
            'revisionType': 'S3',
            's3Location': {
                'bucket': s3Bucket,
                'key': previousKey,
                'bundleType': 'zip',
                'eTag': previousETag
            }
        }
    )
