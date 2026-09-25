import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

import yaml


GITHUB_API = "https://api.github.com"

GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
DISCORD_WEBHOOK = os.environ["DISCORD_WEBHOOK"]
OWNER = os.environ["GITHUB_OWNER"]


# ---------------------------------------------------------
# Load config.yml
# ---------------------------------------------------------

with open("config.yml", "r", encoding="utf-8") as file:
    config = yaml.safe_load(file) or {}


EXCLUDED_REPOS = set(
    config.get("excluded_repos", [])
)

EVENTS = config.get(
    "events",
    ["push", "pull_request"]
)


# ---------------------------------------------------------
# GitHub API
# ---------------------------------------------------------

def github_request(
    url,
    method="GET",
    data=None,
):
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "discord-webhook-manager",
    }

    body = None

    if data is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(data).encode("utf-8")

    request = urllib.request.Request(
        url,
        data=body,
        headers=headers,
        method=method,
    )

    try:
        with urllib.request.urlopen(request) as response:
            response_body = response.read()

            if not response_body:
                return None

            return json.loads(
                response_body.decode("utf-8")
            )

    except urllib.error.HTTPError as error:
        error_body = error.read().decode(
            "utf-8",
            errors="replace",
        )

        print(
            f"GitHub API error {error.code}: {error_body}",
            file=sys.stderr,
        )

        return None

    except urllib.error.URLError as error:
        print(
            f"Network error: {error}",
            file=sys.stderr,
        )

        return None


# ---------------------------------------------------------
# Get repositories
# ---------------------------------------------------------

def get_repositories():
    repositories = []
    page = 1

    while True:
        params = urllib.parse.urlencode({
            "per_page": 100,
            "page": page,
            "affiliation": "owner",
            "sort": "full_name",
        })

        url = (
            f"{GITHUB_API}/user/repos?{params}"
        )

        result = github_request(url)

        if result is None:
            print("Failed to retrieve repositories.")
            sys.exit(1)

        if not result:
            break

        repositories.extend(result)

        if len(result) < 100:
            break

        page += 1

    return repositories


# ---------------------------------------------------------
# Get existing webhooks
# ---------------------------------------------------------

def get_hooks(repo):
    url = (
        f"{GITHUB_API}/repos/"
        f"{OWNER}/{repo}/hooks"
    )

    result = github_request(url)

    if result is None:
        return []

    return result


# ---------------------------------------------------------
# Find our Discord webhook
# ---------------------------------------------------------

def find_discord_hook(hooks):
    for hook in hooks:
        config = hook.get("config", {})

        if (
            hook.get("name") == "web"
            and config.get("url") == DISCORD_WEBHOOK
        ):
            return hook

    return None


# ---------------------------------------------------------
# Create webhook
# ---------------------------------------------------------

def create_webhook(repo):
    url = (
        f"{GITHUB_API}/repos/"
        f"{OWNER}/{repo}/hooks"
    )

    payload = {
        "name": "web",
        "active": True,
        "events": EVENTS,
        "config": {
            "url": DISCORD_WEBHOOK,
            "content_type": "json",
        },
    }

    result = github_request(
        url,
        method="POST",
        data=payload,
    )

    return result is not None


# ---------------------------------------------------------
# Update webhook
# ---------------------------------------------------------

def update_webhook(repo, hook):
    hook_id = hook["id"]

    url = (
        f"{GITHUB_API}/repos/"
        f"{OWNER}/{repo}/hooks/{hook_id}"
    )

    payload = {
        "active": True,
        "events": EVENTS,
        "config": {
            "url": DISCORD_WEBHOOK,
            "content_type": "json",
        },
    }

    result = github_request(
        url,
        method="PATCH",
        data=payload,
    )

    return result is not None


# ---------------------------------------------------------
# Process repository
# ---------------------------------------------------------

def process_repository(repo):
    if repo in EXCLUDED_REPOS:
        print(f"[SKIP] {repo}")
        return

    print(f"[CHECK] {repo}")

    hooks = get_hooks(repo)

    existing_hook = find_discord_hook(hooks)

    if existing_hook is None:
        if create_webhook(repo):
            print(f"[ADDED] {repo}")
        else:
            print(f"[FAILED] Could not add webhook to {repo}")

        return

    existing_events = set(
        existing_hook.get("events", [])
    )

    desired_events = set(EVENTS)

    if (
        existing_events == desired_events
        and existing_hook.get("active") is True
    ):
        print(f"[OK] {repo}")
        return

    print(f"[UPDATE] {repo}")

    if update_webhook(repo, existing_hook):
        print(f"[UPDATED] {repo}")
    else:
        print(f"[FAILED] Could not update {repo}")


# ---------------------------------------------------------
# Main
# ---------------------------------------------------------

def main():
    print()
    print("================================")
    print(" Discord Webhook Manager")
    print("================================")
    print()

    print(f"Owner: {OWNER}")
    print(
        "Events:",
        ", ".join(EVENTS),
    )

    print(
        "Excluded:",
        ", ".join(EXCLUDED_REPOS)
        if EXCLUDED_REPOS
        else "none",
    )

    print()

    repositories = get_repositories()

    print(
        f"Found {len(repositories)} repositories."
    )

    print()

    for repository in repositories:
        process_repository(
            repository["name"]
        )

    print()
    print("Finished.")


if __name__ == "__main__":
    main()
