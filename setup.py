from setuptools import setup

setup(
    name='mkdocs-drawio-exporter',
    version='0.3.0',
    packages=['mkdocsdrawioexporter'],
    url='https://github.com/LukeCarrier/mkdocs-drawio-exporter',
    license='MIT',
    author='Luke Carrier',
    author_email='luke@carrier.im',
    description='Exports your Draw.io diagrams at build time for easier embedding into your documentation',
    install_requires=['mkdocs'],

    entry_points={
        'mkdocs.plugins': [
            'drawio-exporter = mkdocsdrawioexporter:DrawIoExporter',
        ],
    },
)
