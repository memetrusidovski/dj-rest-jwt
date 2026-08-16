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
    keywords='django rest auth registration rest-framework django-registration api',
    zip_safe=False,
    install_requires=[
        'Django>=4.2',
        'djangorestframework>=3.13.0',
        'djangorestframework-simplejwt>=5.3.0',
        'requests>=2.25.0',
    ],
    extras_require={
        'with-social': ['django-allauth[socialaccount]>=64.0.0'],
        # cryptography encrypts TOTP secrets at rest; qrcode renders the
        # enrolment QR code (without it the activation response just omits it).
        'with-mfa': ['pyotp>=2.9.0', 'cryptography>=41.0.0', 'qrcode>=7.4.0'],
        'with-passkeys': ['webauthn>=2.0.0'],
    },
    test_suite='runtests.runtests',
    include_package_data=True,
    python_requires='>=3.10',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Web Environment',
        'Framework :: Django',
        'Framework :: Django :: 4.2',
        'Framework :: Django :: 5.0',
        'Framework :: Django :: 5.1',
        'Framework :: Django :: 5.2',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Programming Language :: Python :: 3.13',
        'Topic :: Software Development',
        'Topic :: Security',
    ],
)
