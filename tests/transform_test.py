from unittest import TestCase

from nyuki.utils.transform import (
    Upper, Lower, Lookup, Unset, Set, Sub, Extract, Converter,
    FactoryConditionBlock
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

    def test_008_condition_block(self):
        rule = FactoryConditionBlock([
            {'type': 'if', 'condition': "(  @test  == 'test if'   )", 'rules': [
                {'type': 'set', 'fieldname': 'if', 'value': 'ok'}
            ]},
            {'type': 'elif', 'condition': "('test elif' == @test)", 'rules': [
                {'type': 'set', 'fieldname': 'elif', 'value': 'ok'}
            ]},
            {'type': 'elif', 'condition': "(@test == 123456)", 'rules': [
                {'type': 'set', 'fieldname': 'elif 2', 'value': 'ok'}
            ]},
            {'type': 'else', 'rules': [
                {'type': 'set', 'fieldname': 'else', 'value': 'ok'}
            ]}
        ])
        data = {'test': 'test if'}
        rule.apply(data)
        self.assertIn('if', data)
        data = {'test': 'test elif'}
        rule.apply(data)
        self.assertIn('elif', data)
        data = {'test': 123456}
        rule.apply(data)
        self.assertIn('elif 2', data)
        data = {'test': 'test else'}
        rule.apply(data)
        self.assertIn('else', data)

        with self.assertRaises(ValueError):
            FactoryConditionBlock([])
        with self.assertRaises(TypeError):
            FactoryConditionBlock([{'type': 'else'}])
        with self.assertRaises(TypeError):
            FactoryConditionBlock([{'type': 'if'}, {'type': 'if'}])
        with self.assertRaises(TypeError):
            FactoryConditionBlock([{'type': 'if'}, {'type': 'else'}, {'type': 'if'}])
        with self.assertRaises(TypeError):
            FactoryConditionBlock([{'type': 'if'}, {'type': 'if'}, {'type': 'elif'}])

    def test_009a_converter(self):
        rules = [
            Lookup('normal', table={'message': 'lookup'}),
            Lookup('to_upper', table={'uppercase': 'lookup'}),
            Upper('normal'),
            Upper('to_upper'),
        ]
        converter = Converter(rules)
        self.assertEqual(len(converter.rules), 4)
        converter.apply(self.data)
        self.assertEqual(self.data['normal'], 'LOOKUP')
        self.assertEqual(self.data['to_upper'], 'LOOKUP')

    def test_009b_converter_from_dict(self):
        rules = {
            'rules': [
                {'type': 'lookup', 'fieldname': 'normal', 'table': {'message': 'lookup'}},
                {'type': 'lookup', 'fieldname': 'to_upper', 'table': {'uppercase': 'lookup'}},
                {'type': 'upper', 'fieldname': 'normal'},
                {'type': 'upper', 'fieldname': 'to_upper'},
            ]
        }
        converter = Converter.from_dict(rules)
        self.assertEqual(len(converter.rules), 4)
        converter.apply(self.data)
        self.assertEqual(self.data['normal'], 'LOOKUP')
        self.assertEqual(self.data['to_upper'], 'LOOKUP')
