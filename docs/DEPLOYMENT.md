# Deployment: https://www.ayumi.earth

**Configuration prepared; live deployment not established by this document.** The owner approved publishing
the deployment files and push-to-main workflow on November 15, 2026. VM provisioning, account eligibility,
repository secrets, DNS and a successful HTTPS health check remain separate gates. No DNS change or cloud
purchase is performed by this update. The intended production stack uses Docker Compose, Caddy HTTPS and
automatic redeployment on pushes to `main` once its prerequisites exist.

| Piece | Where | Notes |
| --- | --- | --- |
| VM | Proposed Oracle Cloud `VM.Standard.A1.Flex` (Ampere, arm64), Ubuntu 24.04 | Current public Always Free documentation lists 1,500 OCPU-hours / 9,000 GB-hours monthly, equivalent to 2 OCPU / 12 GB for an eligible tenancy; verify account limits and storage eligibility before provisioning. No measured production memory budget is claimed. |
| Stack | `deploy/compose.prod.yaml` | API (3 processes), SAR/evidence worker, AI/evidence worker, Valkey, Caddy. Code baked into the image; runtime data on named volumes that survive redeploys. |
| HTTPS | Caddy (`deploy/Caddyfile`) | Let's Encrypt certificates for `www.ayumi.earth`; `ayumi.earth` redirects to `www`. |
| Redeploy | GitHub Actions (`.github/workflows/deploy.yml`) | On push to `main`: rsync the code to the VM over SSH, `docker compose ... up -d --build`, then check `https://www.ayumi.earth/api/health`. |
| DNS | Porkbun | `A @` and `A www` → VM public IPv4 (`tools/porkbun_dns.py`). |
| Images | `Dockerfile` | arm64 builds use `requirements-linux-arm64-py312.lock` (same versions as the x86-64 lock, arm64 wheel hashes). |

Secrets never enter the repository: the app keys live only in `~/ayumi/.env` on the VM, the deploy key only in
GitHub Actions secrets, and the Porkbun keys only in the shell that runs the DNS script.

## 1. Oracle Cloud VM (owner, once)

1. Review [Oracle's current Always Free limits](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm)
   and account/billing terms before creating an account. Eligibility, available capacity and usage above limits vary.
   Pick a home region suitable for the actual users;
   it cannot be changed later.
2. Console → *Compute → Instances → Create instance*:
   - Name `ayumi`. Image: **Canonical Ubuntu 24.04** (aarch64). Shape: *Ampere* → **VM.Standard.A1.Flex**.
     Select only resources within the verified account allowance (currently documented equivalent: 2 OCPU / 12 GB).
     Capacity may be unavailable; benchmark this stack before claiming the shape is sufficient.
   - Networking: create a new VCN and public subnet, **Assign a public IPv4 address**.
   - SSH keys: **Paste public keys** → an owner-controlled public key. Keep the private key outside Git; never assume a local key has already been created.
   - Boot volume: 100–200 GB.
3. Open HTTP/HTTPS in the cloud firewall: *Networking → Virtual cloud networks → (VCN) → Security Lists → Default
   Security List → Add Ingress Rules*: source `0.0.0.0/0`, TCP, destination ports `80,443` (and UDP 443 optional).
4. Send the instance's **public IPv4** to the assistant.

## 2. VM setup (assistant, over SSH)

```bash
scp -i .local/deploy/admin_ed25519 deploy/setup-vm.sh ubuntu@<IP>:
ssh -i .local/deploy/admin_ed25519 ubuntu@<IP> "bash setup-vm.sh '$(cat .local/deploy/deploy_ed25519.pub)'"
```

This installs Docker, opens ports 80/443 in the OS firewall, creates `~/ayumi/.env` (empty keys, mode 600) and
authorises the deploy key.

## 3. Application keys on the VM (owner, manual)

```bash
ssh ubuntu@<IP>          # or the Oracle Cloud Shell / instance console
nano ~/ayumi/.env
```

Fill in, then save (Ctrl+O, Enter, Ctrl+X):

| Variable | Value |
| --- | --- |
| `GEMINI_API_KEY` | Google AI Studio key (the same one used locally) |
| `EARTHDATA_USERNAME` / `EARTHDATA_PASSWORD` | NASA Earthdata Login (needed for the NISAR GCOV reads) |
| `RAIZ_AI_PROVIDER` | `gemini` (or `fixture` to run without AI) |

Apply changes with `cd ~/ayumi && docker compose -f deploy/compose.prod.yaml up -d` (no rebuild needed).

## 4. GitHub Actions secrets (owner, once)

Repository → *Settings → Secrets and variables → Actions → New repository secret*:

| Name | Value |
| --- | --- |
| `DEPLOY_HOST` | VM public IPv4 |
| `DEPLOY_USER` | `ubuntu` |
| `DEPLOY_SSH_KEY` | full content of `.local/deploy/deploy_ed25519` (private key, including the BEGIN/END lines) |
| `DEPLOY_KNOWN_HOSTS` | output of `ssh-keyscan -t ed25519 <IP>` (the assistant prepares it in `.local/deploy/known_hosts`) |

Then *Actions → Deploy → Run workflow* (or push to `main`).

## 5. DNS on Porkbun (assistant, with the owner's API key)

Owner: Porkbun → *Account → API Access* → create an API key (keep the API key and secret), and on
*Domain Management → ayumi.earth → Details* turn **API Access** on. Then:

```bash
PORKBUN_API_KEY=pk1_... PORKBUN_SECRET_KEY=sk1_... python tools/porkbun_dns.py <IP>          # dry run
PORKBUN_API_KEY=pk1_... PORKBUN_SECRET_KEY=sk1_... python tools/porkbun_dns.py <IP> --apply  # change DNS
```

This removes Porkbun's parking records/URL forwards on `@` and `www` and creates `A` records to the VM. Caddy
obtains the certificates automatically once DNS resolves (usually within minutes).

## Operations

- Logs: `ssh ubuntu@<IP> 'cd ~/ayumi && docker compose -f deploy/compose.prod.yaml logs -f --tail 100'`
- Restart: `docker compose -f deploy/compose.prod.yaml restart`
- Performance log: `docker compose -f deploy/compose.prod.yaml exec api python tools/perf_report.py /var/raiz/logs/perf.jsonl --since 3600`
- Optional cache warm-up after a deploy: set `RAIZ_DEM_PREFETCH=1` in `.env` and restart the API.
- Rollback: revert the commit on `main` and push; the workflow redeploys the previous code. Volumes (caches, jobs,
  artifacts, certificates) are kept.
