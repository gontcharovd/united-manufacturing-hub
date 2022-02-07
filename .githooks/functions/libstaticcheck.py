"""
This file provides go linting by running go vet
"""
import json
import os.path
import re
import subprocess
from pathlib import Path

from .git import Git
from .helper import Progressbar
from .ilib import LibInterface
from .log import Log


class LibStaticCheck(LibInterface):
    projects = []
    build_outcomes = []

    def __init__(self):
        # Check if current branch has upstream
        # If so, only check changed projects
        # If not check all projects

        go_projects = []

        if Git.has_upstream():
            changes = Git.get_committed_changes()
            for change in changes:
                path = f"{Git.get_repository_root()}/{change}"
                if change.endswith(".go"):
                    if not os.path.isfile(path):
                        Log.warn(f"Skipping non-existing file {path}")
                    else:
                        xpath = os.path.dirname(os.path.abspath(path))
                        matches = re.search(r"golang\\cmd\\([\w|-]+)", xpath)
                        if matches is not None:
                            go_projects.append(matches.group(1))
        else:
            go_files = list(Path(Git.get_repository_root()).rglob('*.go'))
            for path in go_files:
                if not os.path.isfile(path):
                    Log.warn(f"Skipping non-existing file {path}")
                else:
                    xpath = os.path.dirname(os.path.abspath(path))
                    matches = re.search(r"golang\\cmd\\([\w|-]+)", xpath)
                    if matches is not None:
                        go_projects.append(matches.group(1))

        go_projects = list(dict.fromkeys(go_projects))
        self.projects.extend(go_projects)

    def check(self):
        repo_root = Git.get_repository_root()
        ly = len(self.projects)
        if ly == 0:
            Log.info("No go projects to check")
            return

        Log.info(f"Checking {ly} go projects")

        pb = Progressbar(ly)

        for project in self.projects:
            project_path = f"{repo_root}/golang/cmd/{project}/"
            if not os.path.isdir(project_path):
                pb.add_progress()
                continue
            p = subprocess.Popen(['staticcheck', '-f', 'json', project_path], stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=f"{repo_root}/golang/")
            output, err = p.communicate()
            rc = p.returncode

            data = output.decode('utf-8')
            data = os.linesep.join([s for s in data.splitlines() if s])

            messages = []
            for line in data.splitlines():
                messages.append(json.loads(line))

            self.build_outcomes.append({
                "rc": rc,
                "message": messages,
                "name": project
            })

            pb.add_progress()
        pb.finish()

    def report(self):
        if len(self.build_outcomes) == 0:
            return 0
        errors = 0
        for outcomes in self.build_outcomes:
            if outcomes["rc"] != 0:
                Log.info(f"{outcomes['name']}")
                prev_file = ""
                for v in outcomes["message"]:
                    if v["severity"] == "error":
                        if prev_file != v["location"]["file"]:
                            prev_file = v["location"]["file"]
                            Log.info(f"\t{os.path.basename(prev_file)}")
                        Log.fail(f"\t\t{v['code']}: {v['message']} ({v['location']['file']}:{v['location']['line']})")
                        errors += 1

        if errors > 0:
            print()
            failstr = f"|| staticcheck failed with {errors} errors ||"
            fstrlen = len(failstr)
            Log.fail('=' * fstrlen)
            Log.fail(failstr)
            Log.fail('=' * fstrlen)
        else:
            Log.ok("======================")
            Log.ok(f"Go vet succeeded")
            Log.ok("======================")
        return errors

    def run(self):
        """
        Runs check & report
        :return: reports return value
        """
        self.check()
        return self.report()