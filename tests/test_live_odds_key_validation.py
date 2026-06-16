import unittest

from autonomous_betting_agent.live_odds import looks_like_placeholder_key, validate_api_key


class LiveOddsKeyValidationTests(unittest.TestCase):
    def test_placeholder_keys_are_rejected(self):
        for key in ['', 'your_real_odds_api_key', 'api_key_here', 'placeholder_key', 'demo_key']:
            self.assertTrue(looks_like_placeholder_key(key))
            with self.assertRaises(RuntimeError):
                validate_api_key(key)

    def test_non_placeholder_key_shape_is_allowed(self):
        key = 'valid_non_secret_odds_key_value_123456789'
        self.assertFalse(looks_like_placeholder_key(key))
        self.assertEqual(validate_api_key(key), key)


if __name__ == '__main__':
    unittest.main()
