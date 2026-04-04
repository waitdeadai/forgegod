"""Utility functions — intentionally messy for refactoring benchmarks."""


def process_data(data, mode, flag=False, extra=None):
    """Process data in various modes. Intentionally long and messy."""
    results = []
    if mode == "filter":
        for item in data:
            if isinstance(item, dict):
                if "value" in item:
                    if item["value"] > 0:
                        if flag:
                            results.append(item["value"] * 2)
                        else:
                            results.append(item["value"])
                    else:
                        if extra and extra.get("include_negative"):
                            results.append(item["value"])
            elif isinstance(item, (int, float)):
                if item > 0:
                    results.append(item)
    elif mode == "transform":
        for item in data:
            if isinstance(item, str):
                results.append(item.upper().strip())
            elif isinstance(item, (int, float)):
                results.append(item * 10)
            elif isinstance(item, dict):
                transformed = {}
                for k, v in item.items():
                    if isinstance(v, str):
                        transformed[k] = v.lower()
                    else:
                        transformed[k] = v
                results.append(transformed)
    elif mode == "aggregate":
        total = 0
        count = 0
        for item in data:
            if isinstance(item, (int, float)):
                total += item
                count += 1
            elif isinstance(item, dict) and "value" in item:
                total += item["value"]
                count += 1
        if count > 0:
            results = [{"total": total, "count": count, "average": total / count}]
        else:
            results = [{"total": 0, "count": 0, "average": 0}]
    elif mode == "validate":
        for item in data:
            if isinstance(item, dict):
                valid = True
                if "name" not in item:
                    valid = False
                if "email" not in item:
                    valid = False
                elif "@" not in item.get("email", ""):
                    valid = False
                if valid:
                    results.append(item)
    return results


def format_output(data, fmt="text"):
    """Format data for output."""
    if fmt == "text":
        lines = []
        for item in data:
            if isinstance(item, dict):
                parts = [f"{k}={v}" for k, v in item.items()]
                lines.append(", ".join(parts))
            else:
                lines.append(str(item))
        return "\n".join(lines)
    elif fmt == "csv":
        if not data:
            return ""
        if isinstance(data[0], dict):
            headers = list(data[0].keys())
            lines = [",".join(headers)]
            for item in data:
                lines.append(",".join(str(item.get(h, "")) for h in headers))
            return "\n".join(lines)
        return "\n".join(str(item) for item in data)
    return str(data)
