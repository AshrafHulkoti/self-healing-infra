#!/usr/bin/python3

import boto3
from slack_webhook import Slack
import sys
from datetime import datetime,timedelta

db = sys.argv[1]
slack = Slack(url='https://hooks.slack.com/services/xxxx')
cloudwatch = boto3.client('cloudwatch')
client=boto3.client('rds')
r53_client = boto3.client('route53')
db_name=db.split("LowBurstBalance-")[-1]
db_endpoint=client.describe_db_instances(
        DBInstanceIdentifier=db_name)['DBInstances'][0]['Endpoint']['Address']

# Get list of instances in cluster
instances=client.describe_db_instances(
        DBInstanceIdentifier=db_name,
    )['DBInstances'][0]['ReadReplicaDBInstanceIdentifiers']
if instances != []:
    instances_list=[db_name]
    instances_list.extend(instances)
else:
    source_instance = client.describe_db_instances(
        DBInstanceIdentifier=db_name,
    )['DBInstances'][0]['ReadReplicaSourceDBInstanceIdentifier']
    instances_list=[source_instance]
    replicas = client.describe_db_instances(
        DBInstanceIdentifier=source_instance,
    )['DBInstances'][0]['ReadReplicaDBInstanceIdentifiers']
    instances_list.extend(replicas)

instances_url=[]

for each in range(len(instances_list)):
    instances_url.append(client.describe_db_instances(
        DBInstanceIdentifier=instances_list[each])['DBInstances'][0]['Endpoint']['Address']
    )
print("Endpoints for the db instances = ", instances_url)

# Find new weights for weighted r53 policy
current_weight_list=[]

# Get current assigned weight for db
def record_details(endpoint): 
    paginator = r53_client.get_paginator('list_resource_record_sets')
    source_zone_records = paginator.paginate(HostedZoneId='xxxxxx')
    for record_set in source_zone_records:
        for record in record_set['ResourceRecordSets']:
            if record['ResourceRecords'][0]['Value'] == endpoint:
                return record['Weight']

for each in range(len(instances_list)):
    weight=record_details(instances_url[each])
    current_weight_list.append(weight)
    if instances_list[each]==db_name:
        db_weight=weight

print('Current weights', current_weight_list)

weight_adjustment=10//(len(instances_list)-1)
print("Weight to be adjusted from other db instances in cluster = ", weight_adjustment)

#increase weight of issue db by 10% and balance other weights
if db_weight <= 50:
    for each in range(len(instances_list)):
        if instances_list[each]==db_name:
            response = r53_client.change_resource_record_sets(
                        HostedZoneId='xxxxxx',
                        ChangeBatch= {
                                            'Comment': 'weight_update',
                                            'Changes': [
                                                {
                                                'Action': "UPSERT",
                                                'ResourceRecordSet': {
                                                    'Name': "hackathon-read.rdsamazonaws.com",
                                                    'Type': "CNAME",
                                                    'TTL': 60,
                                                    'Weight': (current_weight_list[each]+10),
                                                    'SetIdentifier': "record"+str(each+1),
                                                    'ResourceRecords': [{'Value': db_endpoint}]
                                                }
                                }]
                        })
        else:
            response = r53_client.change_resource_record_sets(
                        HostedZoneId='xxxxx',
                        ChangeBatch= {
                                            'Comment': 'weight_update',
                                            'Changes': [
                                                {
                                                'Action': "UPSERT",
                                                'ResourceRecordSet': {
                                                    'Name': "hackathon-read.rdsamazonaws.com",
                                                    'Type': "CNAME",
                                                    'TTL': 60,
                                                    'Weight': (current_weight_list[each]-weight_adjustment),
                                                    'SetIdentifier': "record"+str(each+1),
                                                    'ResourceRecords': [{'Value': instances_url[each]}]
                                                }
                                }]
                        })
    

    print("Weight of db instances Adjusted as per IOPS load of db instances in cluster")
else:
    print("Weight Update cancelled TOO much to change - MANUAL INVERVENTION SUGGESTED")
    message=" " + '\n' + \
    "======================================================" + '\n' + \
    "Weight Update cancelled for " + db_name + " CHECK NEEDED "  + '\n' + \
    "======================================================"
    slack.post(text=message)