import json
import os
from urllib.parse import quote

import urllib3

http = urllib3.PoolManager()

_DIMENSION_TO_RESOURCE_TYPE = {
    "DBInstanceIdentifier": "rds_instance",
    "InstanceId": "ec2_instance",
    "LoadBalancer": "load_balancer",
    "ClusterName": "eks_cluster",
}

_ALERT_VISUALS = {
    "OK": {
        "emoji": ":white_check_mark:",
        "text": "RESOLVED",
        "color": "#32a852",
        "wording": "*_==== May the force be with you ====_*",
    },
    "ALARM": {
        "emoji": ":fire:",
        "text": "FIRING",
        "color": "#ad1721",
        "wording": "*_==You don't know the power of the dark side==_*",
    },
    "INSUFFICIENT_DATA": {
        "emoji": ":warning:",
        "text": "INSUFFICIENT_DATA",
        "color": "#d9a404",
        "wording": "*_==Signal unclear. Check the telemetry==_*",
    },
}

_DEFAULT_ALERT_VISUALS = {
    "emoji": ":warning:",
    "text": "UNKNOWN",
    "color": "#6b7280",
    "wording": "*_==Unknown alarm state detected==_*",
}


def _extract_region_code(alarm_arn):
    arn_parts = alarm_arn.split(":")
    return arn_parts[3] if len(arn_parts) > 3 else ""


def _infer_resource(trigger):
    for dimension in trigger.get("Dimensions", []):
        dimension_name = dimension.get("name", "")
        if dimension_name in _DIMENSION_TO_RESOURCE_TYPE:
            return _DIMENSION_TO_RESOURCE_TYPE[dimension_name], dimension.get("value", "unknown")
    return "unknown", "unknown"


def _build_openclaw_block(alarm_msg, environment):
    alarm_name = alarm_msg["AlarmName"]
    account_id = alarm_msg["AWSAccountId"]
    region_code = _extract_region_code(alarm_msg.get("AlarmArn", ""))
    resource_type, resource_name = _infer_resource(alarm_msg.get("Trigger", {}))

    lines = [
        "--- Structured Alert ---",
        "schema_version: v1",
        "source: cloudwatch_alarm",
        "status: {0}".format(alarm_msg["NewStateValue"]),
        "alert_name: {0}".format(alarm_name),
        "account_id: {0}".format(account_id),
        "region_code: {0}".format(region_code),
        "environment: {0}".format(environment),
        "event_time: {0}".format(alarm_msg.get("StateChangeTime", "")),
        "alert_key: cloudwatch_alarm:{0}:{1}:{2}".format(account_id, region_code, alarm_name),
        "resource_type: {0}".format(resource_type),
        "resource_name: {0}".format(resource_name),
    ]
    return "\n".join(lines)


def _get_alert_visuals(alarm_state):
    return _ALERT_VISUALS.get(alarm_state, _DEFAULT_ALERT_VISUALS)


def _build_cloudwatch_console_url(alarm_msg):
    region_code = _extract_region_code(alarm_msg.get("AlarmArn", ""))
    alarm_name = quote(alarm_msg.get("AlarmName", ""), safe="")
    return (
        "https://{0}.console.aws.amazon.com/cloudwatch/home?region={0}#alarmsV2:alarm:{1}".format(
            region_code,
            alarm_name,
        )
    )


def lambda_handler(event, context):
    url = os.environ['SLACK_WEBHOOK_URL']
    alert_environment = os.environ['ALERT_ENV']
    alarm_msg = json.loads(event['Records'][0]['Sns']['Message'])
    alarm_name = alarm_msg['AlarmName']
    alarm_state = alarm_msg['NewStateValue']
    alarm_account = alarm_msg['AWSAccountId']
    alarm_region = alarm_msg['Region']
    alarm_desc = alarm_msg['NewStateReason']
    alarm_time = alarm_msg['StateChangeTime']
    alert_visuals = _get_alert_visuals(alarm_state)
    openclaw_block = _build_openclaw_block(alarm_msg, alert_environment)
    msg = {
        "channel": os.environ['SLACK_WEBHOOK_CHANNEL'],
        "username": os.environ['SLACK_WEBHOOK_USERNAME'],
        "text": alert_visuals["wording"],
        "icon_emoji" : os.environ['SLACK_WEBHOOK_ICON'],
        "attachments": [
        {
            "color": alert_visuals["color"],
            "attachment_type": "default",
            "text": "{0} [*{1}*] \n *AWS Account :* {2} \n *AWS Region :* {7} \n *AlarmName :* {3} \n *Time :* {4} \n *status :* {5} \n *message :* {6} \n\n{8}\n".format(
                alert_visuals["emoji"],
                alert_visuals["text"],
                alarm_account,
                alarm_name,
                alarm_time,
                alarm_state,
                alarm_desc,
                alarm_region,
                openclaw_block,
            ),
            "actions": [
                {
                    "name": "CloudWatchAlarm",
                    "text": "Go to CloudWatch Alarm",
                    "type": "button",
                    "style": "primary",
                    "url": _build_cloudwatch_console_url(alarm_msg)
                }]
        }
    ]
    }
    encoded_msg = json.dumps(msg).encode('utf-8')
    resp = http.request('POST', url, body=encoded_msg, timeout=urllib3.Timeout(connect=3.0, read=10.0))
    if resp.status >= 400:
        raise RuntimeError("Slack webhook failed with status {0}".format(resp.status))
    print({
        "message_output": json.loads(event['Records'][0]['Sns']['Message']),
        "AlarmName": alarm_name,
        "AlarmStatus" : alarm_state,
        "status_code": resp.status, 
        "response": resp.data
    })
