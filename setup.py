from setuptools import setup, find_packages


long_description = open('README.md').read()

setup(
    name='zm-py',
    version='0.5.0',
    license='Apache Software License',
    url='https://github.com/rohankapoorcom/zm-py',
    author='Rohan Kapoor',
    author_email='rohan@rohankapoor.com',
    description='A loose python wrapper around the ZoneMinder REST API.',
    long_description=long_description,
    long_description_content_type='text/markdown',
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    platforms='any',
    install_requires=list(val.strip() for val in open('requirements.txt')),
    classifiers=[
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ]
)
