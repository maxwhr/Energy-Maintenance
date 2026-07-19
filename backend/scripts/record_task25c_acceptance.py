from __future__ import annotations

import argparse

from task25c_common import now_iso, write_json


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", action="append", default=[], metavar="NAME=STATUS")
    args = parser.parse_args()
    results = {}
    for item in args.result:
        if "=" not in item:
            raise SystemExit(f"invalid result: {item}")
        name, status = item.split("=", 1)
        results[name.strip()] = status.strip()
    write_json("acceptance_results.json", {"generated_at": now_iso(), "results": results})
    print("RECORDED", len(results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
