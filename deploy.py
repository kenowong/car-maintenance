import subprocess, json, os, urllib.request, urllib.error

REPO = "car-maintenance"
DESC = "汽车维修保养记录与智能提醒：双维度(日期/里程)保养提醒、多车档案、维保凭证、养车成本统计。支持 NAS 部署与手机独立使用(PWA)。"
BASE = r"E:\WorkBuddy\2026-09-02-13-23-20\car-maintenance"

def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, cwd=BASE, **kw)

def get_token(host):
    GM = r"C:/Users/OFFICE/.workbuddy/binaries/PortableGit/versions/1.2.0/mingw64/bin/git-credential-manager.exe"
    p = subprocess.run([GM, "get"], input=f"protocol=https\nhost={host}\n", capture_output=True, text=True)
    for line in p.stdout.splitlines():
        if line.startswith("password="):
            return line.split("=", 1)[1].strip()
    return None

gitee_token = get_token("gitee.com")
github_token = get_token("github.com")
print("Gitee token :", ("found " + gitee_token[:4] + "...") if gitee_token else "MISSING")
print("GitHub token:", ("found " + github_token[:4] + "...") if github_token else "MISSING")

def gitee_create():
    if not gitee_token:
        return "skip"
    url = "https://gitee.com/api/v1/user/repos?access_token=" + gitee_token
    data = json.dumps({"name": REPO, "description": DESC, "private": False}).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        return urllib.request.urlopen(req, timeout=25).status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception as e:
        return "ERR:" + str(e)[:80]

def github_create():
    if not github_token:
        return "skip"
    url = "https://api.github.com/user/repos"
    data = json.dumps({"name": REPO, "description": DESC, "private": False}).encode()
    req = urllib.request.Request(url, data=data, headers={
        "Authorization": "Bearer " + github_token,
        "Content-Type": "application/json",
        "Accept": "application/vnd.github+json",
        "User-Agent": "git"
    }, method="POST")
    try:
        return urllib.request.urlopen(req, timeout=25).status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception as e:
        return "ERR:" + str(e)[:80]

print("Gitee create :", gitee_create())
print("GitHub create:", github_create())

# ===== 本地 git =====
run(["git", "init"])
run(["git", "config", "user.name", "kenowong"])
run(["git", "config", "user.email", "kenowong@me.com"])
run(["git", "add", "-A"])
ci = run(["git", "commit", "-m", "init: 车管家汽车维保记录应用 (单文件PWA + NAS后端)"])
print("commit:", ci.returncode, (ci.stdout or ci.stderr)[-200:])
run(["git", "branch", "-M", "main"])

# ===== Gitee (SSH 已验证可用) =====
r = run(["git", "remote", "add", "gitee", "git@gitee.com:kenowong/car-maintenance.git"])
if r.returncode != 0:
    run(["git", "remote", "set-url", "gitee", "git@gitee.com:kenowong/car-maintenance.git"])
p = run(["git", "push", "-u", "gitee", "main"])
print("Gitee push:", p.returncode, (p.stdout + p.stderr)[-400:])

# ===== GitHub (https + token 注入，不写 config) =====
if github_token:
    os.environ["GIT_CONFIG_COUNT"] = "1"
    os.environ["GIT_CONFIG_KEY_0"] = "url.https://kenowong:" + github_token + "@github.com/.insteadOf"
    os.environ["GIT_CONFIG_VALUE_0"] = "https://github.com/"
    r = run(["git", "remote", "add", "github", "https://github.com/kenowong/car-maintenance.git"])
    if r.returncode != 0:
        run(["git", "remote", "set-url", "github", "https://github.com/kenowong/car-maintenance.git"])
    p = run(["git", "push", "-u", "github", "main"])
    print("GitHub push:", p.returncode, (p.stdout + p.stderr)[-400:])
else:
    print("GitHub push: skipped (no token)")
