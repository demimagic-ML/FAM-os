"""Immutable identities for release-owned natural integration templates."""


PYTHON_API_RECIPE_ID = "integration.python.root-api@1.0.0"
STATIC_SITE_RECIPE_ID = "integration.python.static-http@1.0.0"
POSTGRESQL_IMAGE_REF = "postgres:17-alpine"
POSTGRESQL_IMAGE_SHA256 = (
    "742f40ea20b9ff2ff31db5458d127452988a2164df9e17441e191f3b72252193"
)
POSTGRESQL_HEALTH_RECIPE_ID = "integration.postgres.pg-isready.v1"
PYTHON_API_SECRET_CONSUMER_ID = "integration:python-api"
POSTGRESQL_SECRET_CONSUMER_ID = "integration:postgresql"
