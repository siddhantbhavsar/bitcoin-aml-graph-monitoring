INVESTIGATION_SCHEMA = {
    "name": "aml_investigation_summary",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "alert_id": {"type": "string"},
            "txId": {"type": "string"},
            "severity": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
            "risk_score": {"type": "integer"},
            "executive_summary": {"type": "string"},
            "why_flagged": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1
            },
            "likely_typologies": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": ["aggregation", "distribution", "layering", "service_activity", "unknown"]
                },
                "minItems": 1
            },
            "recommended_next_steps": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 2
            },
            "evidence": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "field": {"type": "string"},
                        "value": {},
                        "note": {"type": "string"}
                    },
                    "required": ["field", "value", "note"]
                },
                "minItems": 3
            },
            "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
            "confidence_rationale": {"type": "string"},
            "limitations": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1
            }
        },
        "required": [
            "alert_id",
            "txId",
            "severity",
            "risk_score",
            "executive_summary",
            "why_flagged",
            "likely_typologies",
            "recommended_next_steps",
            "evidence",
            "confidence",
            "confidence_rationale",
            "limitations"
        ]
    }
}
