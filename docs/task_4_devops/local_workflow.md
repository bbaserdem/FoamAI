# Local Workflow

Yes — you can (and should) run Terraform entirely from your laptop before wiring it into a CI job.
Below is a succinct, copy-paste-ready checklist that lets you validate every layer of the deployment pipeline locally.

````markdown
## Local Terraform Test Workflow

### 1  Install & Configure
1. Install **Terraform ≥ 1.8** (`brew install terraform` or binary download).  
2. Install **AWS CLI** and run `aws configure` with your *personal* access key (use an unprivileged IAM user).  
3. Verify:  
   ```bash
   terraform -version
   aws sts get-caller-identity
````

### 2  Set Up a Local Backend

1. Keep state local for MVP:

   ```hcl
   terraform {
     backend "local" {
       path = "terraform.tfstate"
     }
   }
   ```
2. (Optional) Point to **S3** once you trust the config; the backend switch is a one-line change.

### 3  Dry-Run Everything

1. `terraform init` → downloads AWS provider.
2. `terraform fmt -check` and `terraform validate` → catches syntax errors.
3. `terraform plan` → shows the resources that *would* be created.

### 4  Create & Inspect

1. `terraform apply -auto-approve` → actually spins up the `c7i.2xlarge`.
2. Watch the console output; note the **public IP** in the final `Apply complete!` summary.
3. SSH in:

   ```bash
   ssh ubuntu@<public_ip>
   docker ps     # confirm your compose stack is running
   ```

### 5  Tear Down

1. When done, reclaim budget:

   ```bash
   terraform destroy -auto-approve
   ```

   *Always destroy before leaving for the day while you’re iterating.*

### 6  Iterate Quickly

| Need to test…             | Command                                                              |
| ------------------------- | -------------------------------------------------------------------- |
| Only the user-data script | `terraform apply -refresh=false -replace="aws_instance.openfoam_vm"` |
| A single resource change  | `terraform apply -target=aws_security_group.mvp_sg`                  |
| New variable values       | Edit `terraform.tfvars`; run `plan` again                            |

### 7  Optional Local-Only Emulation

| Option                | When to use                                                    | Caveat                                      |
| --------------------- | -------------------------------------------------------------- | ------------------------------------------- |
| **LocalStack**        | Validate that Terraform syntax is correct without touching AWS | Not all EC2 features supported (no real VM) |
| **Vagrant/Multipass** | Test the cloud-init & Docker install script on a local VM      | Does *not* exercise Terraform AWS provider  |

### 8  Lock It In

1. Commit the working `.tf` files and `user_data.sh`.
2. Add `.terraform.lock.hcl` to version control for repeatable provider versions.
3. Set `TF_VAR_...` secrets in **GitHub Secrets**; your Actions workflow can now run `terraform plan` the same way you did locally.

---

#### Quick Sanity Checklist Before Pushing to CI

* [ ] `terraform fmt` shows no diffs.
* [ ] `terraform validate` passes.
* [ ] `terraform plan` outputs **0 to add** after a destroy/apply cycle.
* [ ] VM boots, Docker stack is healthy, `/ping` endpoint returns `pong`.
* [ ] You can destroy everything with one command.

If every box is ticked, plug the same commands into GitHub Actions and you’ll get identical results—just automated.

```
```

