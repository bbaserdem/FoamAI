# 🐧 Using the One-Week DevOps Plan on NixOS

This addendum shows exactly **what to change (or watch out for)** when you follow the
local-test checklist on a NixOS workstation and run
all commands inside a `nix develop` shell provided by a flake.

---

## 0️⃣ TL;DR – Biggest Differences

| Area | “Vanilla Linux” Step | NixOS-Specific Tweak |
|------|----------------------|----------------------|
| Installing CLI tools | `brew install terraform awscli` | Put `terraform`, `awscli2`, `docker`, `docker-buildx`, `openssh`, `jq` in your **devShell**. |
| Docker daemon | Already running on most distros | Enable `virtualisation.docker.enable = true;` in `configuration.nix` **and** add yourself to the `docker` group. |
| Binary plugins (Terraform providers) | Written to `~/.terraform.d` | Works as-is; just keep state and plugin cache **outside the Nix store**. |
| Secrets | `$HOME/.aws/credentials` or env vars | Same, but avoid committing secrets into the flake; use `direnv` or `sops-nix`. |
| Multi-arch buildx | Requires manual install | Add `docker-buildx` to the shell; it registers the plugin automatically. |

---

## 1️⃣ Sample `flake.nix`

```nix
{
  description = "Dev shell for CFD MVP DevOps tasks";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-24.05";
  inputs.flake-utils.url = "github:numtide/flake-utils";

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };
      in {
        devShells.default = pkgs.mkShell {
          name = "cfd-devops-shell";

          packages = with pkgs; [
            terraform
            awscli2
            docker-client           # CLI
            docker-buildx           # buildx plugin
            openssh
            jq
            tflint                  # optional linter
          ];

          shellHook = ''
            export TF_PLUGIN_CACHE_DIR="$HOME/.terraform.d/plugin-cache"
            mkdir -p "$TF_PLUGIN_CACHE_DIR"
            echo "🚀  DevOps shell ready. Run 'terraform init' to start."
          '';
        };
      });
}
````

> **Tip:** add `.envrc` with `use flake .` and run `direnv allow`
> so the shell loads automatically when you `cd` into the repo.

---

## 2️⃣ Enable Docker on NixOS (once)

Edit `/etc/nixos/configuration.nix`:

```nix
virtualisation.docker.enable = true;
users.groups.docker.members = [ "yourusername" ];  # logout/login afterwards
```

```bash
sudo nixos-rebuild switch
```

---

## 3️⃣ Adjusted Day-by-Day Checklist

| Original Day                  | Vanilla Action             | NixOS Replacement                                        |
| ----------------------------- | -------------------------- | -------------------------------------------------------- |
| **Day 1 – step 1**            | Install CLIs               | `nix develop` (flake above)                              |
| **Day 1 – step 3**            | `aws configure`            | Same (creates `~/.aws/` in \$HOME)                       |
| **Day 2 – step 1**            | `terraform init`           | Same, inside dev shell                                   |
| **Day 3 – user-data**         | Cloud-init installs Docker | **Still required** (VM is Ubuntu, not NixOS)             |
| **Day 5 – GH Actions buildx** | install buildx plugin      | Not needed locally; already in shell via `docker-buildx` |
| **Iterate quickly**           | `terraform apply …`        | Same commands                                            |

---

## 4️⃣ Tips for Nix-Friendly Secrets

1. **Never** put AWS keys or OpenAI tokens in the flake or `configuration.nix`.
2. Use one of:

   * `direnv` + `dotenv` – keep a private `.env` outside git.
   * `sops-nix` if you want the secret decrypted at shell enter time.
3. In GitHub Actions you’ll still load secrets from **repository → Settings → Secrets**.

---

## 5️⃣ Common Pitfalls on NixOS

| Symptom                                       | How to Fix                                                                   |
| --------------------------------------------- | ---------------------------------------------------------------------------- |
| `docker: command not found` inside shell      | Add `docker-client` (CLI) *and* enable daemon in `configuration.nix`.        |
| `Cannot connect to the Docker daemon`         | Add user to `docker` group **and relog** or `sudo systemctl restart docker`. |
| Terraform plugin install fails (read-only FS) | Ensure `TF_PLUGIN_CACHE_DIR` points to `$HOME`, not inside `/nix/store`.     |
| AWS CLI credential chain not found            | Verify `$HOME/.aws/credentials` is readable *inside* the devShell.           |

---

## 6️⃣ Quick Validation on NixOS

```bash
direnv allow                # loads dev shell
terraform init
terraform validate
terraform plan              # no errors? great.

nix develop -c aws sts get-caller-identity  # proves AWS creds visible
nix develop -c docker version               # talks to system daemon
```

If all four commands succeed, you can proceed exactly as in the
original seven-day plan — the only difference is you used **Nix** to
get a reproducible toolchain instead of `brew` or `apt`.

---

*Copy this section into `docs/nixos_devops_notes.md` and share it with
any teammate who uses NixOS.*

```
```

