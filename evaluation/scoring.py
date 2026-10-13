"""Independent fixture scoring. No judge model or self-reported success."""
from .scenarios import ScoringKey


def score_response(response, key: ScoringKey):
    errors = [field for field, expected in key.required_fields.items()
              if field not in response or type(response[field]) is not type(expected)
              or response[field] != expected]
    # bool and int compare equal in Python: explicit type checks prevent a
    # numeric '1' from masquerading as an honestly confirmed operation.
    return {"success": not errors, "failed_fields": errors,
            "metric_tags": list(key.metric_tags), "mistake_key": key.mistake_key}
