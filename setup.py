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

name, version = 'zc.ngi', '1.1.4'

import os
from setuptools import setup, find_packages

def read(*rnames):
    return open(os.path.join(os.path.dirname(__file__), *rnames)).read()

long_description=(
        read('README.txt')
        + '\n' +
        'Detailed Documentation\n'
        '**********************\n'
        + '\n' +
        read('src', 'zc', 'ngi', 'README.txt')
        + '\n' +
        read('src', 'zc', 'ngi', 'blocking.txt')
        + '\n' +
        read('src', 'zc', 'ngi', 'adapters.txt')
        + '\n' +
        read('src', 'zc', 'ngi', 'async.txt')
        + '\n' +
        'Download\n'
        '**********************\n'
        )

open('documentation.txt', 'w').write(long_description)

setup(
    name = name, version=version,
    author = "Jim Fulton",
    author_email = "jim@zope.com",
    description = "Network Gateway Interface",
    license = "ZPL 2.1",
    keywords = "network",
    url='http://www.python.org/pypi/'+name,
    long_description=long_description,

    packages = find_packages('src'),
    include_package_data = True,
    package_dir = {'':'src'},
    namespace_packages = ['zc'],
    install_requires = ['setuptools'],
    extras_require = dict(
        test = ['zope.testing'],
        ),
    zip_safe = False,
    )
