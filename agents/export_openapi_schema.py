from app import app
from fastapi.openapi.utils import get_openapi

with open("open-api-schema.json", mode="w") as f:
    import json

    f.write(
        json.dumps(
            get_openapi(
                title="Agents for Bedrock Sample",
                version="1.0.0",
                openapi_version="3.0.0",
                routes=app.routes,
            )
        )
    )
