from setuptools import find_packages, setup

setup(
    name='trex_stl_lib',
    version='0.4',
    description='Trex Stateless library',

    url='https://github.com/shmir/trex_stl_lib',
    author='Yoram Shamir',
    author_email='shmir@ignissoft.com',
    license='Apache',
    zip_safe=False,

    packages=find_packages(),
    include_package_data=True,

    install_requires=[
        'scapy',
        'simpy',
        'pyzmq',
        'texttable',
        'pyyaml',
        'jsonrpclib-pelix',
        'pytest'
    ],
)
