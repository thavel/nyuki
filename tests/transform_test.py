from unittest import TestCase

from nyuki.transform import Upper, Lower, Lookup, Unset, Set, Sub, Extract


class TestTransformCases(TestCase):

    def setUp(self):
        self.data = {
            'normal': 'message',
            'to_upper': 'uppercase',
            'to_lower': 'LOWERCASE',
            'regex': '123message456'
        }

    def test_001_extract(self):
        rule = Extract('regex', r'(?P<new_field>message)')
        rule.apply(self.data)
        self.assertEqual(self.data['new_field'], 'message')

    def test_002_sub(self):
        rule = Sub('regex', r'(?P<new_field>message)', 'hello')
        rule.apply(self.data)
        self.assertEqual(self.data['regex'], '123hello456')

    def test_003_set(self):
        rule = Set('new_field', value='hello')
        rule.apply(self.data)
        self.assertEqual(self.data['new_field'], 'hello')

    def test_004_unset(self):
        rule = Unset('normal')
        rule.apply(self.data)
        self.assertFalse('normal' in self.data)

    def test_005_lookup(self):
        table = {'message': 'lookup'}
        rule = Lookup('normal', table=table)
        rule.apply(self.data)
        self.assertEqual(self.data['normal'], 'lookup')

    def test_006_lower(self):
        rule = Lower('to_lower')
        rule.apply(self.data)
        self.assertEqual(self.data['to_lower'], 'lowercase')

    def test_007_upper(self):
        rule = Upper('to_upper')
        rule.apply(self.data)
        self.assertEqual(self.data['to_upper'], 'UPPERCASE')
