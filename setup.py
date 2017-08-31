##############################################################################
#
# Copyright (c) Zope Foundation and Contributors.
# All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.1 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE.
#
##############################################################################

name = 'zc.ngi'
version = '2.1.0'

from setuptools import setup, find_packages

readme = (
    open('README.rst').read()
    + '\n' +
    open('CHANGES.rst').read()
    + '\n')

tests_require = ['zope.testing', 'manuel']

classifiers = """\
Intended Audience :: Developers
License :: OSI Approved :: MIT License
Programming Language :: Python
Programming Language :: Python :: 2
Programming Language :: Python :: 2.7
Programming Language :: Python :: Implementation :: CPython
""".strip().split('\n')

setup(
    name = name, version=version,
    author = "Jim Fulton",
    author_email = "jim@zope.com",
    description = readme.split('\n', 1)[0],
    license = "ZPL 2.1",
    keywords = ["networking", "testing"],
    url='http://packages.python.org/'+name,
    long_description=readme,
    tests_require = tests_require,
    test_suite = 'zc.ngi.tests.test_suite',

    packages = find_packages('src'),
    include_package_data = True,
    package_dir = {'':'src'},
    namespace_packages = ['zc'],
    install_requires = ['setuptools'],
    extras_require = dict(test=tests_require),
    zip_safe = False,
    classifiers=classifiers,
    )
