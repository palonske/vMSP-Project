from datetime import datetime, timezone


def fix_date(data_dict):
    date_str = data_dict.get("last_updated")
    if date_str and isinstance(date_str, str):
        data_dict["last_updated"] = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    return data_dict

def get_timestamp():
    timestamp = datetime.now(timezone.utc).isoformat(timespec='seconds').replace("+00:00", "Z")
    return timestamp