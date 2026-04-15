from dataclasses import dataclass, field
from typing import Any


@dataclass
class NormalizedAlertEvent:
    # required
    schema_version: str
    source: str
    status: str
    environment: str
    region_code: str
    alert_name: str
    alert_key: str
    resource_type: str
    resource_name: str
    summary: str
    event_time: str
    # optional
    account_id: str = ""
    cluster: str = ""
    severity: str = ""
    namespace: str = ""
    metric_name: str = ""
    description: str = ""
    raw_text: str = ""
    raw_payload: dict[str, Any] = field(default_factory=dict)
