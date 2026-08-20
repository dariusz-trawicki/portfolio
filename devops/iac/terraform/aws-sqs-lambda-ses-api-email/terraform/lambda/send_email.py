import json
import os

import boto3

ses = boto3.client("ses")


def handler(event, context):
    print("Received event:", json.dumps(event))

    records = event.get("Records", [])

    for record in records:
        try:
            message_body = json.loads(record["body"])

            to_addr = message_body.get("to")
            subject = message_body.get("subject")
            body = message_body.get("body")

            if not to_addr or not subject or not body:
                print("Invalid message, missing fields:", message_body)
                continue

            response = ses.send_email(
                Source=os.environ["SES_FROM_EMAIL"],
                Destination={"ToAddresses": [to_addr]},
                Message={
                    "Subject": {"Data": subject, "Charset": "UTF-8"},
                    "Body": {
                        "Text": {"Data": body, "Charset": "UTF-8"},
                        # You can also add HTML if you need it:
                        # "Html": {"Data": f"<p>{body}</p>", "Charset": "UTF-8"},
                    },
                },
            )

            print("Email sent:", response.get("MessageId"))

        except Exception as e:
            print("Error processing record:", e)
            # throw an error so SQS/Lambda can handle retry / DLQ.
            raise

    return {"statusCode": 200, "body": json.dumps({"message": "Processed"})}
