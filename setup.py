from setuptools import setup

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name='civilpy',
    version='0.0.5',
    description='Civil Engineering Tools in Python',
    url="https://daneparks.com/Dane/civilpy",
    author_email="Dane@daneparks.com",
    author="Dane Parks",
    py_modules=['civilpy', 'civilpy.state.ohio'],
    package_dir={'civilpy': 'civilpy'},
    packages=[
        "civilpy.structural",
        "civilpy.construction",
        "civilpy.environmental",
        "civilpy.general",
        "civilpy.geotechnical",
        "civilpy.state",
        "civilpy.state.ohio",
        "civilpy.transportation",
        "civilpy.water_resources"
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "License :: OSI Approved :: MIT License",
        "Environment :: Console :: Curses",
    ],
    long_description=long_description,
    long_description_content_type="text/markdown",
    install_requires=[
        "numpy>=1.22.3",
        "folium>=0.12.1",
        "pandas>=1.4.2",
        "Pillow>=9.1.0",
        "Pint>=0.19.2",
    ],
    extras_require = {
        "dev": [
            "pytest>=3.7",
            "jupyter>=1.0.0",
        ]
    }
)
