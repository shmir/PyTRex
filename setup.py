from setuptools import find_packages, setup


with open('requirements.txt') as f:
    required = f.read().splitlines()
install_requires = [r for r in required if r and r[0] != '#' and not r.startswith('git')]

setup(
    name='pytrex',
    version='0.5',
    description='Trex Stateless library',

    url='https://github.com/shmir/trex_stl_lib',
    author='Yoram Shamir',
    author_email='shmir@ignissoft.com',
    license='Apache',
    zip_safe=False,

    packages=find_packages(),
    include_package_data=True,

    install_requires=install_requires,
    tests_require=['pytest'],
)
