#!/usr/bin/env python

from pip.req import parse_requirements
from setuptools import setup, find_packages


with open('VERSION.txt') as fp:
    version = fp.read().strip()

# Requirements
install_reqs = parse_requirements('requirements.txt', session='dummy')
reqs = [str(ir.req) for ir in install_reqs]

setup(
    name='nyuki',
    version=version,
    description='Nyuki library',
    author='Optiflows R&D',
    author_email='rand@surycat.com',
    install_requires=reqs,
    packages=find_packages(exclude=['tests']),
    test_suite="tests",
)
