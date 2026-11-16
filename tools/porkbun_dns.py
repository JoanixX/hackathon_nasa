"""Point ayumi.earth and www.ayumi.earth at the production VM through the Porkbun API v3.

Keys are read from the environment, never from the repository:
  PORKBUN_API_KEY=pk1_... PORKBUN_SECRET_KEY=sk1_... python tools/porkbun_dns.py <vm-ipv4> [--apply]
Without --apply it only shows the planned changes. Removes the parking/forwarding records on the apex and www
(A, AAAA, ALIAS, CNAME) and creates A records to the VM. Other records (MX, TXT...) are left untouched.
"""

from __future__ import annotations

import ipaddress
import json
import os
import sys

import httpx

DOMAIN = "ayumi.earth"
API = "https://api.porkbun.com/api/json/v3"
HOSTS = ("", "www")  # apex and www
REPLACE_TYPES = {"A", "AAAA", "ALIAS", "CNAME"}


def dns_plan(records: list[dict], ipv4: str) -> tuple[list[dict], list[str]]:
    """Plan only apex/www records; preserve mail, verification and unrelated subdomains."""
    ip = str(ipaddress.IPv4Address(ipv4))
    names = {DOMAIN: "", f"www.{DOMAIN}": "www"}
    stale = [r for r in records if r.get("name") in names and r.get("type") in REPLACE_TYPES
             and not (r.get("type") == "A" and r.get("content") == ip)]
    present = {r.get("name") for r in records if r.get("type") == "A" and r.get("content") == ip}
    return stale, [h for n, h in names.items() if n not in present]


def call(path: str, **body) -> dict:
    keys = {"apikey": os.environ["PORKBUN_API_KEY"], "secretapikey": os.environ["PORKBUN_SECRET_KEY"]}
    r = httpx.post(f"{API}/{path}", json={**keys, **body}, timeout=30)
    data = r.json()
    if data.get("status") != "SUCCESS":
        raise SystemExit(f"Porkbun {path}: {data.get('message', r.text)[:300]}")
    return data


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    ip = str(ipaddress.IPv4Address(sys.argv[1]))
    apply = "--apply" in sys.argv
    call("ping")
    records = call(f"dns/retrieve/{DOMAIN}")["records"]
    stale, to_create = dns_plan(records, ip)
    print(json.dumps({"delete": [(r["type"], r["name"], r["content"]) for r in stale], "create_A": [f"{h or '@'} -> {ip}" for h in to_create]}, indent=1))
    try:
        fwd = [f for f in call(f"domain/getUrlForwarding/{DOMAIN}").get("forwards", []) if f.get("subdomain", "") in (*HOSTS, "@")]
    except SystemExit:
        fwd = []
    if fwd:
        print("URL forwards to remove:", [(f["subdomain"], f["location"]) for f in fwd])
    if not apply:
        print("Dry run: add --apply to change DNS.")
        return
    for f in fwd:
        call(f"domain/deleteUrlForward/{DOMAIN}/{f['id']}")
    for r in stale:
        call(f"dns/delete/{DOMAIN}/{r['id']}")
    for h in to_create:
        call(f"dns/create/{DOMAIN}", name=h, type="A", content=ip, ttl="600")
    print("DNS updated.")


if __name__ == "__main__":
    main()
