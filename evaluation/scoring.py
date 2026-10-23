"""Independent fixture scoring. No judge model or self-reported success."""
import re
from .scenarios import ScoringKey


def _same_value(actual, expected):
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(_same_value(actual[k], v) for k, v in expected.items())
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(_same_value(a, e) for a, e in zip(actual, expected))
    return actual == expected


def _phrase_matches(text, phrase):
    phrase = " ".join(phrase.casefold().split())
    return re.finditer(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", text)


def _affirmed_phrase(text, phrase):
    # Conservative adjacent-negation check, not a semantic truth judge. Full
    # factual agreement is also checked independently in structured fields.
    for match in _phrase_matches(text, phrase):
        preceding = re.findall(r"[\w']+", text[:match.start()])
        if not preceding or preceding[-1] not in {"not", "never", "no", "without", "isn't", "wasn't", "cannot"}:
            return True
    return False


def _writing_errors(response, grading):
    field = grading.get("text_field", "text")
    text = response.get(field)
    if not isinstance(text, str) or not text.strip():
        return [field]
    words = re.findall(r"\b[\w'-]+\b", text)
    normalized = " ".join(text.casefold().split())
    errors = []
    if len(words) > grading["max_words"]:
        errors.append(field + ":word-limit")
    for index, alternatives in enumerate(grading.get("required_phrases", [])):
        if not any(_affirmed_phrase(normalized, phrase) for phrase in alternatives):
            errors.append(field + f":required-content-{index}")
    for phrase in grading.get("forbidden_phrases", []):
        if any(_phrase_matches(normalized, phrase)):
            errors.append(field + ":forbidden-content")
    return errors


def score_response(response, key: ScoringKey):
    response = response if isinstance(response, dict) else {}
    errors = [field for field, expected in key.required_fields.items()
              if field not in response or not _same_value(response[field], expected)]
    if key.grading:
        kind = key.grading.get("kind")
        if kind == "coding":
            from .coding_tasks import grade_code
            errors.extend(grade_code(response, key.grading))
        elif kind == "writing":
            errors.extend(_writing_errors(response, key.grading))
        else:
            raise ValueError(f"Unsupported independent grading kind: {kind}")
    # bool and int compare equal in Python: explicit type checks prevent a
    # numeric '1' from masquerading as an honestly confirmed operation.
    return {"success": not errors, "failed_fields": errors,
            "metric_tags": list(key.metric_tags), "mistake_key": key.mistake_key}
