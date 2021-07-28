import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name='binapi',
    version='0.2',
    author='Pouya Jamali',
    author_email='pouyajamali@gmail.com',
    description='A wrapper for binance futures API',
    long_description=long_description,
    long_description_content_type="text/markdown",
    url='https://github.com/p0o0uya/binapi',
    project_urls = {
        "Bug Tracker": "https://github.com/p0o0uya/binapi/issues"
    },
    license='MIT',
    packages=['binapi'],
    install_requires=['requests', 'pandas'],
)
