#coding=utf8
__author__ = 'Alexander.Li'

from setuptools import setup

setup(
    name='torasync',
    version='0.0.0.1 pre',
    packages=['torasync'],
    author='Alexander.Li',
    author_email='superpowerlee@gmail.com',
    license='LGPL',
    install_requires=["tornado>=2.4.1",],
    description="Run task asynchronously in other processes in easy way",
    keywords ='tornado asynchronous multiprocess',
    url="https://github.com/ipconfiger/torasync"
)