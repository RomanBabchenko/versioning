#!/usr/local/bin/python
import gitlab
import json
import argparse
import os
import re


def version_up(version, kind):
    version = [major, minor, patch, *pre] = re.split(r'\W+', version)
    major, minor, patch = map(lambda x: int(x), version[:3])
    if len(version) == 3:
        pre_ver = 0
    if len(pre) > 0:
        try:
            pre_ver = int(pre[-1])
        except ValueError:
            print('Version format error.')
            return
    if kind == 'major':
        major += 1
        minor, patch, pre_ver = 0, 0, 0
    elif kind == 'minor':
        minor += 1
        patch, pre_ver = 0, 0
    elif kind == 'patch':
        patch += 1
        pre_ver = 0
    elif kind == 'prerelease':
        pre_ver += 1
    if len(pre):
        pre[-1] = pre_ver
        pre = f"{'.'.join([str(x) for x in pre])}"
    else:
        pre = pre_ver
    return f"{major}.{minor}.{patch}-{pre}"


def more_than(one, another):
    one = [int(n) for n in re.split(r'[^\w]', one)]
    another = [int(n) for n in re.split(r'[^\w]', another)]
    print(one, another)
    for i in range(len(one)):
        if one[i] > another[i]:
            return True
    return False


def get_latest_version(data):
    max_ver = sorted([re.split(r'[^\w]', x) for x in data.keys()], key=lambda x: (int(x[0]), int(x[1]), int(x[2]), int(x[3])))[-1]
    return f'{max_ver[0]}.{max_ver[1]}.{max_ver[2]}-{max_ver[3]}'
    # return '-'.join(sorted([x.split('-') for x in data.keys()], key=lambda x: (x[0], int(x[1])))[-1])


def save(file, data, branch, version, current_hash, changelog):
    data[project_id]["branches"][branch]["versions"][version] = {"commit": current_hash, "changelog": changelog}
    print(json.dumps(data[project_id], indent=2))
    file.content = json.dumps(data, indent=2)
    file.save(branch='main', commit_message='Update testfile')


def commits_log(project_id, save_changelog_path, start, end):
    project = gl.projects.get(project_id)
    result = project.repository_compare(start, end)
    # print("CHANGE LOG:")
    # print(json.dumps(result, indent=4, sort_keys=True))
    if result["commits"]:
        with open(save_changelog_path, 'w') as f:
            for commit in result["commits"]:
                f.write(f'DATE: {commit["committed_date"]}\n')
                f.write(f'AUTHOR: {commit["committer_name"]}\n')
                f.write(f'COMMIT_ID: {commit["id"]}\n')
                f.write(f'MESSAGE: {commit["message"]}\n')
    else:
        print('No results in change log.')


def inject_version(path, version):
    with open(path, 'r') as f:
        data = json.load(f)
        data['version'] = version
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)


def version_handler():
    project = gl.projects.get("1974")
    f = project.files.get(file_path='projects.json', ref='main')

    # get the base64 encoded content
    data = json.loads(f.decode())

    # data = json.load(open('projects.json'))

    try:
        if data[project_id]["branches"][branch]:
            latest = get_latest_version(data[project_id]["branches"][branch]["versions"])
            last_commit = data[project_id]['branches'][branch]['versions'][latest]['commit']
            if more_than(current_version, latest):
                version = f"{version_core}-0"
            else:
                version = version_up(latest, 'prerelease')
            start, end = data[project_id]['branches'][branch]['versions'][latest]['changelog'][-84:].strip().split('..')
            if data[project_id]['branches'][branch]['versions'][latest]['commit'] != current_hash:
                changelog = f"git log  {last_commit}..{current_hash}"
                print('cmd:', changelog)
                if CI_COMMIT_MESSAGE.startswith("Merge branch") or more_than(current_version, latest):
                    save(f, data, branch, version, current_hash, changelog)
                    inject_version(inject_version_into, version)
                    start, end = last_commit, current_hash
                else:
                    print('Only merge commits will be processed.')
                    version = latest
                    inject_version(inject_version_into, version)
            else:
                print('Latest commit is the same as current.')
            commits_log(project_id, save_changelog_path, start, end)

    except KeyError as err:
        if str(err) == repr(project_id):
            print(f"Project doesn't exist. Creating new entry for project_id: {project_id})")
            data[project_id] = {"branches": {branch: {"versions": dict()}}}
        if str(err) == repr(branch):
            print(f"Branch doesn't exist. Creating new entry for project_id: {project_id})")
            data[project_id]["branches"][branch] = {"versions": dict()}
        changelog = f"git log  {current_hash}^1..{current_hash}"
        save(f, data, branch, f"{version_core}-0", current_hash, changelog)
        inject_version(inject_version_into, f"{version_core}-0")
        commits_log(project_id, save_changelog_path, f"{current_hash}^1", current_hash)


if __name__ == "__main__":
    URL = os.environ['GITLAB_API_URL']
    API_KEY = os.environ['GITLAB_API_KEY']
    CI_COMMIT_MESSAGE = os.environ['CI_COMMIT_MESSAGE']
    parser = argparse.ArgumentParser()
    parser.add_argument('--project-id', required=True, help='Corresponding Project id for versioning')
    parser.add_argument('--current-version', required=True, help='Current version of application')
    parser.add_argument('--branch', required=True, help='Project branch')
    parser.add_argument('--current-hash', required=True, help='CI commit')
    parser.add_argument('--save-changelog-path', help='Comparison log save path')
    parser.add_argument('--inject-version-into', help='Path to package.json file for injecting new version')

    args = parser.parse_args()

    project_id = args.project_id
    current_version = args.current_version[1:-1]
    version_core = '.'.join(re.split(r'\W+', current_version)[:3])
    branch = args.branch
    current_hash = args.current_hash
    save_changelog_path = args.save_changelog_path
    inject_version_into = args.inject_version_into

    gl = gitlab.Gitlab(url=URL, private_token=API_KEY)
    version_handler()