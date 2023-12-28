import json

from mangum.handlers.utils import maybe_encode_body
from mangum.types import LambdaConfig, LambdaContext, LambdaEvent, Response, Scope


class AgentsForBedrock:
    @classmethod
    def infer(
        cls, event: LambdaEvent, context: LambdaContext, config: LambdaConfig
    ) -> bool:
        return "agent" in event

    def __init__(
        self, event: LambdaEvent, context: LambdaContext, config: LambdaConfig
    ) -> None:
        self.event = event
        self.context = context
        self.config = config

    @property
    def body(self) -> bytes:
        items = {}

        requestBody = self.event.get("requestBody", {})
        content = requestBody.get("content", {})
        application_json = content.get("application/json", {})
        properties = application_json.get("properties", [])
        for item in properties:
            items[item["name"]] = item["value"]

        return maybe_encode_body(
            json.dumps(items) if len(items) > 0 else None,
            is_base64=False,
        )

    @property
    def scope(self) -> Scope:
        return {
            "type": "http",
            "method": self.event["httpMethod"],
            "http_version": "1.1",
            "headers": [],
            "path": self.event["apiPath"],
            "scheme": "https",
            "query_string": None,
            "asgi": {"version": "3.0", "spec_version": "2.0"},
            "aws.event": self.event,
            "aws.context": self.context,
        }

    def __call__(self, response: Response) -> dict:
        return {
            "messageVersion": "1.0",
            "response": {
                "actionGroup": self.event["actionGroup"],
                "apiPath": self.event["apiPath"],
                "httpMethod": self.event["httpMethod"],
                "httpStatusCode": response["status"],
                "responseBody": {"application/json": {"body": response["body"]}},
                "sessionAttributes": self.event["sessionAttributes"],
                "promptSessionAttributes": self.event["promptSessionAttributes"],
            },
        }
