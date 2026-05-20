from pydantic import BaseModel


class DependencyHealth(BaseModel):
    ok: bool
    detail: str


class HealthResponse(BaseModel):
    status: str
    environment: str
    service: str
    dependencies: dict[str, DependencyHealth]


class LiveResponse(BaseModel):
    status: str
    environment: str
    service: str


class ReadinessResponse(BaseModel):
    status: str
    environment: str
    dependencies: dict[str, DependencyHealth]
