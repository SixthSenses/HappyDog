# /eyes_models/setup.py

from setuptools import setup

setup(
    name='eyes_lib',
    version='0.1.0',
    # find_packages() 대신 패키지 폴더 이름을 직접 지정합니다.
    packages=['eyes_lib'],
    description='A library for pet eye disease classification.'
)