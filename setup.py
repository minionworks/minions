from setuptools import setup, find_packages

setup(
    name='minion-works', 
    version='0.0.1',
    author='Aman, Cheena, Sai',
    author_email='sai@cobuild.tech',
    description='Agents for menial tasks',
    long_description=open('README.md', encoding='utf-8').read(),
    long_description_content_type='text/markdown',
    url='https://github.com/minionworks/minions',
    packages=find_packages(),
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    license='MIT',
    python_requires='>=3.7',
    install_requires=[
        "asyncio",
        "playwright",
        "openai",
        "markdownify",
        "python-dotenv",
        "langchain-core",
        "langchain-core",
        "langchain-openai"
    ],
)
