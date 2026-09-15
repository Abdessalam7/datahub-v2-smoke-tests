import json

def write_resultst_to_file(results_dict, filename):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(results_dict, f, indent=2, ensure_ascii=False)

def overall_status(results_dict) -> bool:
    for section in results_dict.values():
        for entry in section.values():
            if entry.get("status") != "OK":
                return False
    return True
