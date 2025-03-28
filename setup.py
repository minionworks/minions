from setuptools import setup, find_packages

setup(
    name='minion-works', 
    version='0.0.1',
    author='@aman, @cheena, @sai',
    author_email='sai@cobuild.tech',
    description='Agents for Menial tasks',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    url='https://github.com/minionworks/minions', 
    packages=find_packages(),  
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',  # Change license if needed
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.7',
    install_requires=open('requirements.txt').read().splitlines(),
)
