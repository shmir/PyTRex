from setuptools import find_packages, setup


with open('requirements.txt') as f:
    required = f.read().splitlines()
install_requires = [r for r in required if r and r[0] != '#' and not r.startswith('git')]

setup(
    name='pytrex',
    version='0.7.1',
    description='Trex Stateless library',

    url='https://github.com/shmir/PyTRex',
    author='Yoram Shamir',
    author_email='shmir@ignissoft.com',
    license='Apache Software License',
    zip_safe=False,
    packages=find_packages(),
    include_package_data=True,

    install_requires=install_requires,
    classifiers=[
        'Programming Language :: Python',
        'development status 3 - Alpha',
        'Natural Language :: English',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: OS Independent',
        'Topic :: Software Development :: Testing :: Traffic Generation',
        'Programming Language :: Python :: 3.7',
    ]
)
