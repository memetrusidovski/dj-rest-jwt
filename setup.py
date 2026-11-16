#!/usr/bin/env python

import os

from setuptools import find_packages, setup

here = os.path.dirname(os.path.abspath(__file__))
f = open(os.path.join(here, 'README.md'))
long_description = f.read().strip()
f.close()


about = {}
with open('dj_rest_jwt/__version__.py', 'r', encoding="utf8") as f:
    exec(f.read(), about)

setup(
    name='dj-rest-jwt',
    version=about['__version__'],
    author='memetrusidovski',
    author_email='',
    url='https://github.com/memetrusidovski/dj-rest-jwt',
    description='JWT-first, production-ready authentication for Django REST Framework',
    license='MIT',
    packages=find_packages(),
    long_description=long_description,
    long_description_content_type='text/markdown',
    keywords='django jwt authentication allauth headless api rest-framework passkeys mfa',
    zip_safe=False,
    install_requires=[
        'Django>=6.0',
        'djangorestframework>=3.16',
        # The token strategy builds on allauth's JWT internals; widen this
        # range only after the test suite passes against the new release.
        'django-allauth[socialaccount,mfa,headless]>=65.22,<66',
        'PyJWT>=2.8',
        'cryptography>=42',
        'argon2-cffi>=23.1',
        'requests>=2.31',
    ],
    test_suite='runtests.runtests',
    include_package_data=True,
    python_requires='>=3.12',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Web Environment',
        'Framework :: Django',
        'Framework :: Django :: 6.0',
        'Framework :: Django :: 6.1',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.12',
        'Programming Language :: Python :: 3.13',
        'Programming Language :: Python :: 3.14',
        'Topic :: Software Development',
        'Topic :: Security',
    ],
)
