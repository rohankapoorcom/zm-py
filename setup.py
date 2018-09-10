from setuptools import setup, find_packages


long_description = open('README.md').read()

setup(
    name='zm-py',
    version='0.0.1',
    license='MIT',
    url='https://github.com/rohankapoorcom/zm-py',
    author='Rohan Kapoor',
    author_email='rohan@rohankapoor.com',
    description='A loose python wrapper around the Zoneminder REST API.',
    long_description=long_description,
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    platforms='any',
    install_requires=list(val.strip() for val in open('requirements.txt')),
    classifiers=[
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 3',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ]
)