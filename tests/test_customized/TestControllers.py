from mock import mock
from tests.base import BaseTestCase, MockRequests
from mod_test.models import TestPlatform
from mod_regression.models import RegressionTest
from mod_auth.models import Role
from mod_test.models import Fork, Test, TestPlatform
from sqlalchemy import and_
from mod_customized.models import TestFork
from flask import g


@mock.patch('github.GitHub')
class TestControllers(BaseTestCase):
    def create_customize_test_form(self, commit_url, platform, commit_select=['', '']):
        return {'commit_url': commit_url, 'commit_select': commit_select, 'platform': platform, 'add': True}

    def test_customize_test_page_loads_with_no_permission(self, git_mock):
        self.create_user_with_role(self.user_name, self.email, self.user_password, Role.user)
        with self.app.test_client() as c:
            response = c.post('/account/login', data=self.create_login_form_data(self.email, self.user_password))
            response = c.get('/custom/')
            self.assertEqual(response.status_code, 200)
            self.assert_template_used('custom/index.html')
            assert "submit" not in str(response.data)

    def test_customize_test_page_loads_with_permission(self, git_mock):
        self.create_user_with_role(self.user_name, self.email, self.user_password, Role.tester)
        with self.app.test_client() as c:
            response = c.post('/account/login', data=self.create_login_form_data(self.email, self.user_password))
            response = c.get('/custom/')
            self.assertEqual(response.status_code, 200)
            self.assert_template_used('custom/index.html')
            assert "submit" in str(response.data)

    def test_customize_test_fails_with_wrong_commit_url(self, git_mock):
        self.create_user_with_role(self.user_name, self.email, self.user_password, Role.tester)
        with self.app.test_client() as c:
            response = c.post('/account/login', data=self.create_login_form_data(self.email, self.user_password))
            response = c.post('/custom/', data=self.create_customize_test_form('', ['linux']))
            self.assertEqual(response.status_code, 200)
            self.assert_template_used('custom/index.html')
            assert 'Commit url is not filled in' in str(response.data)
            response = c.post('/custom/', data=self.create_customize_test_form('test-url', ['linux']))
            assert 'Invalid URL' in str(response.data)
            response = c.post('/custom/', data=self.create_customize_test_form('https://www.google.com', ['linux']))
            assert 'Wrong Commit URL' in str(response.data)

    @mock.patch('requests.get', side_effect=MockRequests)
    def test_customize_test_uses_same_repo(self, git_mock, mock_requests):
        self.create_user_with_role(self.user_name, self.email, self.user_password, Role.tester)
        with self.app.test_client() as c:
            response = c.post('/account/login', data=self.create_login_form_data(self.email, self.user_password))
            response = c.post('/custom/', data=self.create_customize_test_form(
                'https://www.github.com/test/test_repo/commit/abcdef', ['linux']))
            self.assertEqual(response.status_code, 200)
            self.assert_template_used('custom/index.html')
            assert 'Wrong Commit URL' not in str(response.data)
            response = c.post('/custom/', data=self.create_customize_test_form(
                'https://www.github.com/test/other_repo/commit/abcdef', ['linux']))
            assert 'Wrong Commit URL' in str(response.data)

    @mock.patch('requests.get', side_effect=MockRequests)
    def test_customize_test_creates_with_right_test_commit(self, git_mock, mock_requests):
        self.create_user_with_role(self.user_name, self.email, self.user_password, Role.tester)
        with self.app.test_client() as c:
            response = c.post('/account/login', data=self.create_login_form_data(self.email, self.user_password))
            response = c.post('/custom/', data=self.create_customize_test_form(
                'https://www.github.com/test/test_repo/commit/abcdef', ['linux']))
            self.assertEqual(response.status_code, 200)
            self.assert_template_used('custom/index.html')
            custom_test = TestFork.query.filter(TestFork.user_id == g.user.id).first()
            assert custom_test is not None

    @mock.patch('requests.get', side_effect=MockRequests)
    def test_customize_test_creates_fork_if_not_exists(self, git_mock, mock_requests):
        self.create_user_with_role(self.user_name, self.email, self.user_password, Role.tester)
        with self.app.test_client() as c:
            response = c.post('/account/login', data=self.create_login_form_data(self.email, self.user_password))
            response = c.post('/custom/', data=self.create_customize_test_form(
                'https://www.github.com/test/test_repo/commit/abcdef', ['linux']))
            self.assertEqual(response.status_code, 200)
            self.assert_template_used('custom/index.html')
            fork = Fork.query.filter(Fork.github.like("%/test/test_repo.git")).first()
            assert fork is not None

    @mock.patch('requests.get', side_effect=MockRequests)
    def test_customize_test_creates_with_multiple_platforms(self, git_mock, mock_requests):
        self.create_user_with_role(self.user_name, self.email, self.user_password, Role.tester)
        with self.app.test_client() as c:
            response = c.post('/account/login', data=self.create_login_form_data(
                self.email, self.user_password))
            response = c.post('/custom/', data=self.create_customize_test_form(
                'https://www.github.com/test/test_repo/commit/abcdef', ['linux', 'windows']))
            self.assertEqual(response.status_code, 200)
            self.assert_template_used('custom/index.html')
            test_linux = g.db.query(Test.id).filter(
                and_(TestFork.test_id == Test.id, Test.platform == TestPlatform.linux)).first()
            test_windows = g.db.query(Test.id).filter(
                and_(TestFork.test_id == Test.id, Test.platform == TestPlatform.windows)).first()
            assert test_linux is not None
            assert test_windows is not None

    def test_customize_test_loads_github_commits(self, git_mock):
        self.create_user_with_role(self.user_name, self.email, self.user_password, Role.tester)
        self.set_github_access    
