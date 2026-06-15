from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

import autonomous_betting_agent.local_users as local_users


class LocalUsersTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.original_dir = local_users.LOCAL_USERS_DIR
        local_users.LOCAL_USERS_DIR = Path(self.tmp.name) / 'local_users'

    def tearDown(self) -> None:
        local_users.LOCAL_USERS_DIR = self.original_dir
        self.tmp.cleanup()

    def test_sanitize_user_id(self) -> None:
        self.assertEqual(local_users.sanitize_user_id('John Smith!'), 'john_smith')
        self.assertEqual(local_users.sanitize_user_id(''), 'owner')

    def test_create_and_list_profiles(self) -> None:
        profile = local_users.create_or_update_user('Cody Jenkins', user_id='Cody Main')
        self.assertEqual(profile.user_id, 'cody_main')
        self.assertTrue(local_users.profile_path(profile.user_id).exists())
        profiles = local_users.list_user_profiles()
        ids = {item.user_id for item in profiles}
        self.assertIn('cody_main', ids)
        self.assertIn('owner', ids)

    def test_user_data_path_is_sandboxed_to_user_folder(self) -> None:
        path = local_users.user_data_path('Jane Demo', '../bad name.csv')
        self.assertIn('jane_demo', str(path))
        self.assertEqual(path.name, 'bad_name.csv')

    def test_add_user_columns(self) -> None:
        frame = pd.DataFrame([{'event': 'A at B', 'prediction': 'B'}])
        tagged = local_users.add_user_columns(frame, 'Cody Main', 'Cody')
        self.assertEqual(tagged.loc[0, 'local_user_id'], 'cody_main')
        self.assertEqual(tagged.loc[0, 'local_user_display_name'], 'Cody')
        self.assertNotIn('local_user_id', frame.columns)


if __name__ == '__main__':
    unittest.main()
