from typing import Dict


def _format_labels(labels: Dict[str, str]) -> str:
    if not labels:
        return ""
    parts = []
    for key, value in labels.items():
        safe_value = str(value).replace("\\", "\\\\").replace('"', '\\"')
        parts.append(f'{key}="{safe_value}"')
    return "{" + ",".join(parts) + "}"


def render_prometheus(metrics: Dict[str, float], labels: Dict[str, str]) -> str:
    lines = []
    for name, value in metrics.items():
        lines.append(f"gridbot_{name}{_format_labels(labels)} {value}")
    return "\n".join(lines) + "\n"
