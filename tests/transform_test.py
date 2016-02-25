from unittest import TestCase

from nyuki.transform import (
    _Rule, Upper, Lower, Lookup, Unset, Set, Sub, Extract, Ruler, Converter
)


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

    def test_005a_lookup(self):
        table = {'message': 'lookup'}
        rule = Lookup('normal', table=table)
        rule.apply(self.data)
        self.assertEqual(self.data['normal'], 'lookup')

    def test_005b_loopkup_icase(self):
        table = {'mEsSaGe': 'lookup'}

        rule = Lookup('normal', table=table)
        rule.apply(self.data)
        self.assertEqual(self.data['normal'], 'message')

        rule = Lookup('normal', table=table, icase=True)
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

    def test_008a_ruler(self):
        rules = [
            Upper('normal'),
            Upper('to_upper'),
        ]
        ruler = Ruler(Upper, rules)
        self.assertEqual(ruler.type, 'upper')
        self.assertEqual(len(ruler.rules), 2)
        ruler.apply(self.data)
        self.assertEqual(self.data['normal'], 'MESSAGE')
        self.assertEqual(self.data['to_upper'], 'UPPERCASE')

    def test_008b_ruler_from_dict(self):
        rules = {
            'type': 'lookup',
            'rules': [
                {'fieldname': 'normal', 'table': {'message': 'lookup'}},
                {'fieldname': 'to_upper', 'table': {'uppercase': 'lookup'}},
            ]
        }
        ruler = Ruler.from_dict(rules)
        self.assertEqual(ruler.type, 'lookup')
        self.assertEqual(len(ruler.rules), 2)
        ruler.apply(self.data)
        self.assertEqual(self.data['normal'], 'lookup')
        self.assertEqual(self.data['to_upper'], 'lookup')

    def test_008c_ruler_with_global_params(self):

        class MyTestRule(_Rule):

            def _configure(self, test, g_test):
                self.g_test = g_test

        rules = {
            'type': 'mytestrule',
            'rules': [
                {'test': 'val1', 'fieldname': 'test_field'},
                {'test': 'val2', 'fieldname': 'test_field'},
            ],
            'global_params': {
                'g_test': True
            }
        }

        ruler = Ruler.from_dict(rules)
        for rule in ruler.rules:
            self.assertTrue(rule.g_test)

    def test_009a_converter(self):
        lookups = [
            Lookup('normal', table={'message': 'lookup'}),
            Lookup('to_upper', table={'uppercase': 'lookup'}),
        ]
        lookupruler = Ruler(Lookup, lookups)
        uppers = [
            Upper('normal'),
            Upper('to_upper'),
        ]
        upperruler = Ruler(Upper, uppers)
        converter = Converter([lookupruler, upperruler])
        self.assertEqual(len(converter.rulers), 2)
        converter.apply(self.data)
        self.assertEqual(self.data['normal'], 'LOOKUP')
        self.assertEqual(self.data['to_upper'], 'LOOKUP')

    def test_009b_converter_from_dict(self):
        rulers = {
            'rulers': [
                {
                    'type': 'lookup',
                    'rules': [
                        {
                            'fieldname': 'normal',
                            'table': {'message': 'lookup'}
                        },
                        {
                            'fieldname': 'to_upper',
                            'table': {'uppercase': 'lookup'}
                        },
                    ]
                },
                {
                    'type': 'upper',
                    'rules': [
                        {'fieldname': 'normal'},
                        {'fieldname': 'to_upper'},
                    ]
                }
            ]
        }
        converter = Converter.from_dict(rulers)
        self.assertEqual(len(converter.rulers), 2)
        converter.apply(self.data)
        self.assertEqual(self.data['normal'], 'LOOKUP')
        self.assertEqual(self.data['to_upper'], 'LOOKUP')
