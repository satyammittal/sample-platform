"""
mod_customized Controllers
===================
In this module, users can test their fork branch with customized set of regression tests
"""
from flask import Blueprint, g, request
from github import GitHub, ApiError
from datetime import datetime
from dateutil.relativedelta import relativedelta

from decorators import template_renderer, get_menu_entries
from mod_auth.controllers import login_required, check_access_rights
from mod_auth.models import Role, User
from mod_test.models import Fork, Test, TestType, TestPlatform
from mod_customized.forms import TestForkForm
from mod_customized.models import TestFork
from mod_test.controllers import get_data_for_test, TestNotFoundException
from mod_auth.controllers import fetch_username_from_token
from sqlalchemy import and_

mod_customized = Blueprint('custom', __name__)


@mod_customized.before_app_request
def before_app_request():
    g.menu_entries['custom'] = {
        'title': 'Customize Test',
        'icon': 'code-fork',
        'route': 'custom.index'
    }


@mod_customized.route('/', methods=['GET', 'POST'])
@login_required
@template_renderer()
def index():
    fork_test_form = TestForkForm(request.form)
    username = fetch_username_from_token()
    commit_options = "git"
    if username is not None:
        gh = GitHub(access_token=g.github['bot_token'])
        repository = gh.repos(username)(g.github['repository'])
        # Only commits since last month
        today_date = datetime.now()
        last_month = today_date - relativedelta(months=1)
        commit_since = last_month.isoformat() + 'Z'
        commits = repository.commits().get(since=commit_since)
        commit_arr = []
        for commit in commits:
            commit_url = commit['html_url']
            commit_sha = commit['sha']
            commit_option = ('<a href="{url}">{sha}</a>').format(url=commit_url, sha=commit_sha)
            commit_arr.append((commit_url ,commit_option))
        if len(commit_arr) > 0:
            fork_test_form.commit_select.choices = commit_arr
            commit_options = "loaded"
        else:
            commit_options = "linked"
    if fork_test_form.add.data and fork_test_form.validate_on_submit():
        import re
        import requests
        commit_url = fork_test_form.commit_url.data
        # slicing string based on https://www.github.com/{username}/{repo}/commit/{hash}
        format_string = r'(https://(www.)?)?github.com/(?P<username>\S+)/(?P<repo>\S+)/commit/(?P<hash>\S+)'
        match = re.match(format_string, commit_url)
        if match is not None:
            username = match.group('username')
            repo = match.group('repo')
            if repo == g.github['repository']:
                commit_hash = match.group('hash')
                platforms = fork_test_form.platform.data
                api_url = ('https://api.github.com/repos/{user}/{repo}/commits/{hash}').format(
                    user=username, repo=repo, hash=commit_hash
                )
                response = requests.get(api_url)
                if response.status_code == 404:
                    fork_test_form.commit_url.errors.append('Wrong Commit URL')
                else:
                    add_test_to_kvm(username, repo, commit_hash, platforms)
                    fork_test_form = TestForkForm()
            else:
                fork_test_form.commit_url.errors.append('Wrong Commit URL')
        else:
            fork_test_form.commit_url.errors.append('Wrong Commit URL')
    tests = Test.query.filter(and_(TestFork.user_id == g.user.id, TestFork.test_id == Test.id)).order_by(Test.id.desc()).limit(50).all()
    return {
        'addTestFork': fork_test_form,
        'commit_options': commit_options,
        'tests': tests,
        'TestType': TestType
    }


def add_test_to_kvm(username, repo, commit_hash, platforms):
    fork_url = ('https://github.com/{user}/{repo}.git').format(
        user=username, repo=g.github['repository']
    )
    fork = Fork.query.filter(Fork.github == fork_url).first()
    if fork is None:
        fork = Fork(fork_url)
        g.db.add(fork)
        g.db.commit()
    for platform in platforms:
        platform = TestPlatform.from_string(platform)
        test = Test(platform, TestType.commit, fork.id, 'master', commit_hash)
        g.db.add(test)
        g.db.commit()
        test_fork = TestFork(g.user.id, test.id)
        g.db.add(test_fork)
        g.db.commit()


@mod_customized.route('/<test_id>')
@template_renderer('test/by_id.html')
def by_id(test_id):
    fork_tests = g.db.query(TestFork.test_id).filter(TestFork.user_id == g.user.id).subquery()
    test = Test.query.filter(and_(Test.id == test_id, Test.id.in_(fork_tests))).first()
    if test is None:
        raise TestNotFoundException('Test with id {id} does not exist'.format(id=test_id))

    return get_data_for_test(test)
