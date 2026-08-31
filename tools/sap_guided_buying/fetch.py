"""Fetch an SAP Help Portal deliverable through the help.sap.com JSON content API.

The /docs/... pages are a Vue SPA and serve no content to a plain HTTP client, but the
SPA's own backing endpoints are reachable unauthenticated:

  /http.svc/deliverableMetadata?product_url=..&deliverable_url=..&version=..&language=..&state=..
      -> deliverable id + buildNo
  /http.svc/pagecontent?deliverable_id=..&buildNo=..[&file_path=<loio>.html]
      -> topic body HTML; the call without file_path also carries deliverable.fullToc

Responses are cached per topic so conversion can be iterated without re-hitting SAP.
"""

import argparse
import json
import pathlib
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date

BASE = "https://help.sap.com"
UA = "Mozilla/5.0 (compatible; documentation-export/1.0)"
HERE = pathlib.Path(__file__).resolve().parent

DEFAULTS = {
    "product_url": "buying-invoicing",
    "deliverable_url": "guided-buying-finding-items-and-making-purchases",
    "version": "2608",
    "language": "en-US",
}


def get_json(path, params, attempts=5):
    url = f"{BASE}{path}?{urllib.parse.urlencode(params)}"
    delay = 1.0
    for attempt in range(1, attempts + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            if attempt == attempts:
                raise RuntimeError(f"{url} failed after {attempts} attempts: {exc}") from exc
            time.sleep(delay)
            delay *= 2
            continue
        if payload.get("status") != "OK":
            raise RuntimeError(f"{url} -> {payload.get('status')}: {payload.get('message')}")
        return payload["data"]
    raise AssertionError("unreachable")


def flatten_toc(nodes, level=1, out=None):
    """SAP nests children under 'c'. Produce a flat, TOC-ordered topic list."""
    out = [] if out is None else out
    for node in nodes:
        out.append(
            {
                "level": level,
                "title": node["t"],
                "file_path": node["u"],
                "loio": node["u"].rsplit(".", 1)[0],
            }
        )
        flatten_toc(node.get("c") or [], level + 1, out)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for key, value in DEFAULTS.items():
        ap.add_argument(f"--{key.replace('_', '-')}", default=value)
    ap.add_argument("--state", default="PRODUCTION")
    ap.add_argument("--delay", type=float, default=0.3, help="seconds between topic fetches")
    ap.add_argument("--refresh", action="store_true", help="ignore the cache and refetch")
    args = ap.parse_args()

    meta = get_json(
        "/http.svc/deliverableMetadata",
        {
            "product_url": args.product_url,
            "deliverable_url": args.deliverable_url,
            "version": args.version,
            "language": args.language,
            "state": args.state,
        },
    )["deliverable"]
    deliverable_id, build_no = meta["id"], meta["buildNo"]
    print(f"deliverable {deliverable_id} build {build_no} version {meta['version']}")

    landing = get_json(
        "/http.svc/pagecontent",
        {
            "deliverable_id": deliverable_id,
            "buildNo": build_no,
            "loadlandingpageontopicnotfound": "true",
        },
    )
    topics = flatten_toc(landing["deliverable"]["fullToc"])
    print(f"{len(topics)} topics in the table of contents")

    cache = HERE / "cache" / f"{deliverable_id}-{meta['version']}"
    cache.mkdir(parents=True, exist_ok=True)

    errors = []
    for i, topic in enumerate(topics, 1):
        dest = cache / f"{topic['loio']}.json"
        if dest.exists() and not args.refresh:
            continue
        try:
            data = get_json(
                "/http.svc/pagecontent",
                {
                    "deliverable_id": deliverable_id,
                    "buildNo": build_no,
                    "file_path": topic["file_path"],
                    "loadlandingpageontopicnotfound": "true",
                },
            )
        except RuntimeError as exc:
            errors.append({"loio": topic["loio"], "title": topic["title"], "error": str(exc)})
            print(f"  [{i}/{len(topics)}] FAILED {topic['title']}: {exc}", file=sys.stderr)
            continue
        dest.write_text(
            json.dumps(
                {"title": data["currentPage"]["t"], "body": data["body"]},
                indent=1,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        print(f"  [{i}/{len(topics)}] {topic['title']}")
        time.sleep(args.delay)

    manifest = {
        "title": landing["deliverable"]["title"],
        "shortdesc": landing["deliverable"].get("shortdesc", ""),
        "product_url": args.product_url,
        "deliverable_url": args.deliverable_url,
        "deliverable_id": deliverable_id,
        "deliverable_loio": landing["deliverable"]["loio"],
        "version": meta["version"],
        "build_no": build_no,
        "language": args.language,
        "retrieved": date.today().isoformat(),
        "source_url": (
            f"{BASE}/docs/{args.product_url}/{args.deliverable_url}/"
            f"{args.deliverable_url}?version={meta['version']}"
        ),
        "cache_dir": cache.relative_to(HERE).as_posix(),
        "topics": topics,
    }
    manifest_path = HERE / f"manifest-{deliverable_id}-{meta['version']}.json"
    manifest_path.write_text(json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {manifest_path.name}")

    if errors:
        print(f"{len(errors)} topics failed to fetch", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
