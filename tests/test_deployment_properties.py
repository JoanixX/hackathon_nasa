"""Deployment tooling checks never contact DNS, SSH, cloud accounts or live keys."""
import importlib.util
import ipaddress
from pathlib import Path

from hypothesis import given, settings, strategies as st

from conftest import budget

_spec = importlib.util.spec_from_file_location("porkbun", Path(__file__).resolve().parent.parent / "tools/porkbun_dns.py")
dns = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dns)


@settings(max_examples=budget(2000))
@given(st.lists(st.fixed_dictionaries({"id": st.text(max_size=12), "name": st.sampled_from([dns.DOMAIN, "www."+dns.DOMAIN, "mail."+dns.DOMAIN]),
                                      "type": st.sampled_from(["A", "AAAA", "CNAME", "ALIAS", "TXT", "MX"]),
                                      "content": st.text(max_size=40)}), max_size=40),
       st.integers(0, 2**32-1))
def test_dns_plan_preserves_other_records_and_is_idempotent(records, address):
    ip = str(ipaddress.IPv4Address(address))
    before = [dict(r) for r in records]
    stale, create = dns.dns_plan(records, ip)
    assert records == before
    assert all(r["name"] in [dns.DOMAIN, "www."+dns.DOMAIN] and r["type"] in dns.REPLACE_TYPES for r in stale)
    assert not any(r["type"] == "A" and r["content"] == ip for r in stale)
    final = [r for r in records if r not in stale] + [{"name": (h+"." if h else "")+dns.DOMAIN, "type": "A", "content": ip} for h in create]
    assert dns.dns_plan(final, ip) == ([], [])


@settings(max_examples=budget(500))
@given(st.integers(1, 2**32-2))
def test_dns_cli_dry_run_never_mutates(monkeypatch, address):
    calls = []
    def fake_call(path, **body):
        calls.append(path)
        if path.startswith("dns/retrieve"):
            return {"records": [{"id": "old", "name": dns.DOMAIN, "type": "A", "content": "0.0.0.0"}]}
        if "getUrlForwarding" in path:
            return {"forwards": [{"id": "foreign", "subdomain": "mail", "location": "https://example.com"}]}
        return {}
    monkeypatch.setattr(dns, "call", fake_call)
    monkeypatch.setattr(dns.sys, "argv", ["porkbun_dns.py", str(ipaddress.IPv4Address(address))])
    dns.main()
    assert calls == ["ping", "dns/retrieve/"+dns.DOMAIN, "domain/getUrlForwarding/"+dns.DOMAIN]


def test_arm_lock_preserves_all_x86_versions_and_hash_shape():
    import re
    root = Path(__file__).resolve().parent.parent
    def pins(path):
        result = {}
        for line in path.read_text().splitlines():
            if not line.strip() or line.startswith("#"):
                continue
            match = re.fullmatch(r"([a-z0-9_-]+)==([^ ]+) --hash=sha256:([0-9a-f]{64})", line)
            assert match, line
            assert match[1] not in result
            result[match[1]] = match[2]
        return result
    assert pins(root/"requirements-linux-arm64-py312.lock") == pins(root/"requirements-linux-py312.lock")
