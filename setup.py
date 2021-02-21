#!/usr/bin/env python
# encoding: utf-8

"""
Package PyTRex for distribution.
"""

from setuptools import setup, find_packages


def main():

    with open('requirements.txt') as f:
        install_requires = f.read().splitlines()
    with open('README.md') as f:
        long_description = f.read()

    setup(
        name='pytrex',
        description='Python OO API package to automate TRex traffic generator stateless traffic',
        url='https://github.com/shmir/PyTRex/',
        use_scm_version={
            'root': '.',
            'relative_to': __file__,
            'local_scheme': 'node-and-timestamp'
        },

        license='Apache Software License',

        author='Yoram Shamir',
        author_email='yoram@ignissoft.com',

        platforms='any',
        install_requires=install_requires,
        packages=find_packages(exclude=('tests', 'tests.*',)),
        include_package_data=True,

        long_description=long_description,
        long_description_content_type='text/markdown',

        keywords='trex l2l3 test tool automation',

        classifiers=[
            'Development Status :: 5 - Production/Stable',
            'Natural Language :: English',
            'License :: OSI Approved :: Apache Software License',
            'Intended Audience :: Developers',
            'Operating System :: OS Independent',
            'Topic :: Software Development :: Testing',
            'Programming Language :: Python :: 3.7',
            'Programming Language :: Python :: 3.8',
            'Programming Language :: Python :: 3.9'],
    )


if __name__ == '__main__':
    main()
