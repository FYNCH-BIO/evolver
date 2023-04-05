from setuptools import setup
from codecs import open

# Parse the version from the module without importing
version = '0.0.0'
with open('evolver/__init__.py') as f:
    for line in f:
        if line.find('__version__') >= 0:
            version = line.split('=')[1].strip().strip('"').strip("'")
            break

# Retrieve dependencies
with open('requirements.txt', 'r') as f:
    reqs = f.readlines()
with open('test-requirements.txt', 'r') as f:
    test_reqs = f.readlines()

# Retrieve readme
with open('README.rst', 'r') as f:
    long_desc = f.read()

setup(
    name='evolver',
    version=version,
    description='Evolver connection for Fynch-Bio.',
    long_description=long_desc,
    author='Boston University Software & Application Innovation Lab',
    author_email='fjansen@bu.edu',
    url='https://github.com/FYNCH-BIO/evolver',
    packages=['evolver'],
    install_requires=reqs,
    tests_require=test_reqs,
    test_suite='nose.collector',
    classifiers=(
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Topic :: Software Development :: Libraries',
        'Topic :: Utilities',
    ),
)