# Deploy Workflow

Automated commit-test-deploy pipeline with pre-flight checks.

## Steps

1. **Pre-flight checks**
   - Run `git config user.email` and verify it matches the expected deployer for this repo
   - Run `git status` to see what's staged/unstaged/untracked
   - Check for any running builds or stale processes that could interfere

2. **Run tests**
   - Execute the project's test command (check CLAUDE.md or package.json for the correct command)
   - If any tests fail, STOP and report failures. Do not proceed to commit.

3. **Commit**
   - Stage only the relevant changed files (never `git add -A` blindly)
   - Write a descriptive conventional commit message summarizing the changes
   - Do not use `--no-verify`

4. **Push**
   - Push to the correct remote and branch (usually `origin main`)
   - Verify the push succeeded and report the commit hash

5. **Deploy (if Vercel project)**
   - If a `.vercel/` directory or `vercel.json` exists, this is a Vercel project
   - Run `vercel --prod` or confirm the Git-triggered deploy kicked off
   - Wait for deployment and verify the URL returns HTTP 200
   - Report the live deployment URL

6. **Post-deploy verification**
   - Confirm the deployed version matches the commit hash that was pushed
   - Report a summary: commit hash, branch, deployment URL (if applicable), test results

## Guardrails

- NEVER force-push unless explicitly asked
- NEVER skip pre-commit hooks
- If git author email doesn't match expected, warn and ask before proceeding
- If tests fail, report which tests failed and stop -- do not deploy broken code
