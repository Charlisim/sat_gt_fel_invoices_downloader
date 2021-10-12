import setuptools

with open("README.md", "r") as f:
    long_description = f.read()

setuptools.setup(
    name="sat_gt_fel_invoices_downloader",
    version="0.1.0",
    author="Carlos Simon",
    author_email="dev@csimon.dev",
    description="Downloads PDFs and XMLs of invoices (received and emited) to later processing from Guatemalan SAT (Superintendencia de Administración Tributaria)",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/gt-banks-parser/banks-parser-base",
    package_dir={"": "src"},
    packages=setuptools.find_packages(where="src"),
    classifiers=[
        "Programming Language :: Python :: 3.6",
        "Development Status :: 4 - Beta",
        "License :: OSI Approved :: GNU License",
        "Operating System :: OS Independent",
        "Intended Audience :: Financial and Insurance Industry",
        "Intended Audience :: Information Technology",
        "Topic :: Office/Business :: Financial",
        "Topic :: Utilities",
    ],
    python_requires=">=3.6",
    install_requires=["requests", "beautifulsoup4"],
)