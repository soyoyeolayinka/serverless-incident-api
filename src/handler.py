import json
import os
import time
import uuid
from decimal import Decimal

import boto3

TABLE_NAME = os.environ.get("TABLE_NAME", "incidents")
table = boto3.resource("dynamodb").Table(TABLE_NAME)
VALID_SEVERITIES = {"SEV1", "SEV2", "SEV3", "SEV4"}
VALID_STATUSES = {"OPEN", "INVESTIGATING", "MONITORING", "CLOSED"}


def response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(body, default=lambda value: float(value) if isinstance(value, Decimal) else str(value)),
    }


def parse_body(event):
    try:
        return json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return None


def create_incident(event):
    body = parse_body(event)
    if body is None:
        return response(400, {"error": "Request body must be valid JSON"})
    required = ("title", "severity", "service")
    missing = [field for field in required if not body.get(field)]
    if missing:
        return response(400, {"error": f"Missing fields: {', '.join(missing)}"})
    severity = body["severity"].upper()
    if severity not in VALID_SEVERITIES:
        return response(400, {"error": "severity must be SEV1, SEV2, SEV3, or SEV4"})
    now = int(time.time())
    item = {
        "incident_id": str(uuid.uuid4()),
        "title": body["title"].strip(),
        "severity": severity,
        "service": body["service"].strip(),
        "status": "OPEN",
        "created_at": now,
        "updated_at": now,
    }
    table.put_item(Item=item, ConditionExpression="attribute_not_exists(incident_id)")
    return response(201, item)


def get_incident(incident_id):
    result = table.get_item(Key={"incident_id": incident_id})
    if "Item" not in result:
        return response(404, {"error": "Incident not found"})
    return response(200, result["Item"])


def list_incidents():
    result = table.scan(Limit=50)
    return response(200, {"items": result.get("Items", []), "count": result.get("Count", 0)})


def update_incident(event, incident_id):
    body = parse_body(event)
    if body is None:
        return response(400, {"error": "Request body must be valid JSON"})
    status = str(body.get("status", "")).upper()
    if status not in VALID_STATUSES:
        return response(400, {"error": "Invalid status"})
    result = table.update_item(
        Key={"incident_id": incident_id},
        UpdateExpression="SET #status = :status, updated_at = :updated_at",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={":status": status, ":updated_at": int(time.time())},
        ConditionExpression="attribute_exists(incident_id)",
        ReturnValues="ALL_NEW",
    )
    return response(200, result["Attributes"])


def lambda_handler(event, _context):
    method = event.get("requestContext", {}).get("http", {}).get("method", "")
    incident_id = event.get("pathParameters", {}).get("id") if event.get("pathParameters") else None
    try:
        if method == "POST":
            return create_incident(event)
        if method == "GET" and incident_id:
            return get_incident(incident_id)
        if method == "GET":
            return list_incidents()
        if method == "PATCH" and incident_id:
            return update_incident(event, incident_id)
        return response(405, {"error": "Method not allowed"})
    except table.meta.client.exceptions.ConditionalCheckFailedException:
        return response(404, {"error": "Incident not found"})
    except Exception:
        return response(500, {"error": "Internal server error"})
