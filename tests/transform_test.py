from unittest import TestCase

from nyuki.utils.transform import (
    Upper, Lower, Lookup, Unset, Set, Sub, Extract, Converter,
    FactoryConditionBlock, Arithmetic, Union
)


class TestTransformCases(TestCase):

    def setUp(self):
        self.data = {
            'normal': 'message',
            'to_upper': 'uppercase',
            'to_lower': 'LOWERCASE',
            'regex': '123message456',
            'none': None,
        }

    def test_001_extract(self):
        rule = Extract('regex', r'(?P<new_field>message)')
        rule.apply(self.data)
        self.assertEqual(self.data['new_field'], 'message')

        Extract('missing', r'(?P<new_field>message)').apply(self.data)
        self.assertTrue('missing' not in self.data)

        Extract('none', r'(?P<new_field>message)').apply(self.data)
        self.assertIsNone(self.data['none'])

    def test_002_sub(self):
        rule = Sub('regex', r'(?P<new_field>message)', 'hello')
        rule.apply(self.data)
        self.assertEqual(self.data['regex'], '123hello456')

        Sub('missing', r'(?P<new_field>message)', 'hello').apply(self.data)
        self.assertTrue('missing' not in self.data)

        Sub('none', r'(?P<new_field>message)', 'hello').apply(self.data)
        self.assertIsNone(self.data['none'])

    def test_003_set(self):
        rule = Set('new_field', value='hello')
        rule.apply(self.data)
        self.assertEqual(self.data['new_field'], 'hello')

    def test_004_unset(self):
        rule = Unset('normal')
        rule.apply(self.data)
        self.assertFalse('normal' in self.data)

        Unset('missing').apply(self.data)
        self.assertTrue('missing' not in self.data)

        Unset('none').apply(self.data)
        self.assertTrue('none' not in self.data)

    def test_005a_lookup(self):
        table = {'message': 'lookup'}
        rule = Lookup('normal', table=table)
        rule.apply(self.data)
        self.assertEqual(self.data['normal'], 'lookup')

        Lookup('missing', table=table).apply(self.data)
        self.assertTrue('missing' not in self.data)

        Lookup('none').apply(self.data)
        self.assertIsNone(self.data['none'])

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

        Lower('missing').apply(self.data)
        self.assertTrue('missing' not in self.data)

        Lower('none').apply(self.data)
        self.assertIsNone(self.data['none'])

    def test_007_upper(self):
        rule = Upper('to_upper')
        rule.apply(self.data)
        self.assertEqual(self.data['to_upper'], 'UPPERCASE')

        Upper('missing').apply(self.data)
        self.assertTrue('missing' not in self.data)

        Upper('none').apply(self.data)
        self.assertIsNone(self.data['none'])

    def test_008_condition_block(self):
        rule = FactoryConditionBlock([
            {'type': 'if', 'condition': "(  @test  == 'test if'   )", 'rules': [
                {'type': 'set', 'fieldname': 'if', 'value': 'ok'}
            ]},
            {'type': 'elif', 'condition': "('test elif' == @test)", 'rules': [
                {'type': 'set', 'fieldname': 'elif', 'value': 'ok'}
            ]},
            {'type': 'elif', 'condition': "(@test == 123456) and ('ok' == 'ok')", 'rules': [
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

    def test_010a_regexp_error_report(self):
        rule = Extract('regex', r'(.*)')
        diff = rule.apply(self.data)
        self.assertEqual(diff['error'], 'regexp_rule_error')

    def test_011_arithmetic(self):
        data = {
            'string_field_1': 'some string',
            'string_field_2': 'some other string',
            'int_field_1': 10,
            'int_field_2': 20,
            'float_field_1': 0.31,
            'float_field_2': 0.62,
        }
        rule = Arithmetic('result', '+', 5, '@int_field_1')
        rule.apply(data)
        self.assertEqual(data['result'], 15)

        rule = Arithmetic('result', '-', '@float_field_2', '@float_field_1')
        rule.apply(data)
        self.assertEqual(data['result'], 0.31)

        rule = Arithmetic('result', '-', '@int_field_1', '@int_field_2')
        rule.apply(data)
        self.assertEqual(data['result'], -10)

        rule = Arithmetic('result', '*', '@int_field_1', 5)
        rule.apply(data)
        self.assertEqual(data['result'], 50)

        rule = Arithmetic('result', '/', 40, '@int_field_2')
        rule.apply(data)
        self.assertEqual(data['result'], 2)

        rule = Arithmetic('result', '+', '@string_field_1', '@some@string')
        diff = rule.apply(data)
        self.assertEqual(diff['error'], 'arithmetic_rule_error')

    def test_012_union(self):
        data = {
            'dict_field_1': {'a': 1, 'b': 2},
            'dict_field_2': {'a': 10, 'c': 3},
            'list_field_1': [{'a': 1}, {'b': 2}],
            'list_field_2': [{'a': 1}, {'c': 3}],
        }

        rule = Union('result', '@list_field_1', '@list_field_2')
        rule.apply(data)
        self.assertIn({'a': 1}, data['result'])
        self.assertIn({'b': 2}, data['result'])
        self.assertIn({'c': 3}, data['result'])

        rule = Union('result', '@dict_field_1', data['dict_field_2'])
        rule.apply(data)
        self.assertEqual(data['result']['a'], 10)
        self.assertEqual(data['result']['b'], 2)
        self.assertEqual(data['result']['c'], 3)
