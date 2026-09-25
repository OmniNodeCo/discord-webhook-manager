import json
import os
import sys
import urllib.error
import urllib.request

GITHUB_API = "https://api.github.com"
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
DISCORD_WEBHOOK = os.environ["DISCORD_WEBHOOK"]

OWNER = os.environ["GITHUB_OWNER"]

EXCLUDED_REPOS = set()
EVENTS = ["push", "pull_request"]


def api_request(url, method="GET", data=None):
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "discord-webhook-manager",
    }

    if data is not None:
        headers["Content-Type"] = "application/json"

    body = None

    if data is not None:
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

            return json.loads(response_body)

    except urllib.error.HTTPError as error:
        error_body = error.read().decode("utf-8", errors="replace")

        print(
            f"GitHub API error {error.code}: {error_body}",
            file=sys.stderr,
        )

        return None


def get_repositories():
    repositories = []
    page = 1

    while True:
        url = (
            f"{GITHUB_API}/user/repos"
            f"?per_page=100"
            f"&page={page}"
            f"&affiliation=owner"
            f"&sort=full_name"
        )

        result = api_request(url)

        if not result:
            break

        repositories.extend(result)

        if len(result) < 100:
            break

        page += 1

    return repositories


def get_hooks(repo):
    url = f"{GITHUB_API}/repos/{OWNER}/{repo}/hooks"

    result = api_request(url)

    return result or []


def webhook_matches(hook):
    config = hook.get("config", {})

    return (
        config.get("url") == DISCORD_WEBHOOK
        and hook.get("name") == "web"
    )


def create_webhook(repo):
    url = f"{GITHUB_API}/repos/{OWNER}/{repo}/hooks"

    payload = {
        "name": "web",
        "active": True,
        "events": EVENTS,
        "config": {
            "url": DISCORD_WEBHOOK,
            "content_type": "json",
        },
    }

    result = api_request(
        url,
        method="POST",
        data=payload,
    )

    return result is not None


def process_repository(repo):
    if repo in EXCLUDED_REPOS:
        print(f"[SKIP] {repo} is excluded")
        return

    print(f"[CHECK] {repo}")

    hooks = get_hooks(repo)

    for hook in hooks:
        if webhook_matches(hook):
            print(f"[OK] {repo} already has the Discord webhook")
            return

    if create_webhook(repo):
        print(f"[ADDED] Discord webhook added to {repo}")
    else:
        print(f"[ERROR] Could not add webhook to {repo}")


def main():
    print("Discord Webhook Manager")
    print("=======================")

    print(f"Owner: {OWNER}")
    print(f"Events: {', '.join(EVENTS)}")
    print(f"Excluded repositories: {len(EXCLUDED_REPOS)}")
    print()

    repositories = get_repositories()

    if not repositories:
        print("No repositories found.")
        return

    print(f"Found {len(repositories)} repositories.")
    print()

    for repository in repositories:
        name = repository["name"]

        process_repository(name)

    print()
    print("Finished.")


if __name__ == "__main__":
    main()
