#!/usr/bin/env python

import sys
from os.path import dirname, join, realpath

ROOT = realpath(join(dirname(__file__), '..'))
sys.path += (ROOT,)

import subprocess
import slackpy
import re
from github import Github
from botify_saas import VERSION
MAIN_REPO = "release-test"
MAIN_BRANCH = 'master'
TRACK_LABEL = 'track-this'
COMMAND_LABEL = 'when tracking'
SLACK_WEBHOOK = 'https://hooks.slack.com/services/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'
DEFAULT_SLACK_CHANNEL = '#test-tracking-issues'


def execute(command, ignore=False):
    """
    :param command: command to execute
    :type command: string
    :param ignore: if error should be ignored
    :type ignore: bool
    Executes a command and returns the output
    """

    pr = subprocess.Popen(
        command,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)

    (out, error) = pr.communicate()
    if error and not ignore:
        fail("Error: executing '{}', {}".format(command, error))
    return out


def fail(message):
    """
    :param message: message to print
    :type message: string
    prints a message and exits
    """
    print message
    sys.exit(2)


def version_to_str(version_tuple):
    """
    :param version_tuple: tuple representing the versions
    :type version_tuple: tuple
    :return : version as string
    """
    return ".".join((str(i) for i in version_tuple))


def main(argv):
    print "Current version: {}".format(VERSION)
    g = Github("pleasedontbelong@gmail.com", "xxxxxxxxxx")
    repo = g.get_user().get_repo(MAIN_REPO)

    # get last two tags
    lasts = [t.name for t in repo.get_tags()[:2]]

    # PRs between last two tags
    git_log_cmd = 'git log {}..{} {} --merges --pretty=format:"%s"'.format(
        lasts[1],
        lasts[0],
        MAIN_BRANCH
    )
    # TODO ignore case
    pr_number_re = re.compile("pull request #(\d+)")
    br_number_re = re.compile("from .+#(\d+)$")
    issue_number_re = re.compile("fixes #(\d+)$")
    prs = execute(git_log_cmd).split('\n')

    # get the list of fixed issues from the branch name or the PR body
    fixed_issues = []
    for pr in prs:
        # try to get the Issue number from the branch name in the subject
        issue_number = br_number_re.search(pr)
        if issue_number:
            fixed_issues.append(int(issue_number.group(1)))
        else:
            # get the PR number from the subject
            pr_number = pr_number_re.search(pr)
            if not pr_number:
                break
            pr_number = int(pr_number.group(1))

            # try to get the issue number from the body of the PR
            body = repo.get_pull(pr_number).body
            mentioned_issues = issue_number_re.search(body)
            if not mentioned_issues:
                break
            # maybe more than one issue
            for issue in mentioned_issues.groups():
                fixed_issues.append(int(issue))

    # filter issues that should be tracked
    for issue_nb in fixed_issues:
        issue = repo.get_issue(issue_nb)
        # break if issue does not have the correct label to track
        if not any([l.name for l in issue.get_labels() if l.name == TRACK_LABEL]):
            break

        # search a comment with instructions to alert
        # TODO ignore case
        commands = [c.body for c in issue.get_comments() if c.body.startswith(COMMAND_LABEL)]
        if not commands:
            break
        commands = commands[0].split('\n')[1:]
        for command in commands:
            execute_command(command, issue)


def execute_command(command_str, issue):
    if command_str.startswith('alert slack:'):
        alert_slack(command_str[12:], issue)


def alert_slack(who, issue):
    logging = slackpy.SlackLogger(SLACK_WEBHOOK, DEFAULT_SLACK_CHANNEL, 'pleasedontbelong')
    # TODO pass the correct environement
    logging.info(message="Hey {}! We just fixed the <{}|Issue #{}> on staging".format(
        who,
        issue.html_url,
        issue.number
    ))


if __name__ == "__main__":
    main(sys.argv[1:])
