"""
StockDataMaster 安装脚本

支持pip安装和开箱即用两种模式
"""

from setuptools import setup, find_packages
import os


# 读取README
def read_readme():
    readme_path = os.path.join(os.path.dirname(__file__), 'README.md')
    if os.path.exists(readme_path):
        with open(readme_path, 'r', encoding='utf-8') as f:
            return f.read()
    return ""


# 读取版本号
def read_version():
    init_path = os.path.join(os.path.dirname(__file__), '__init__.py')
    with open(init_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.startswith('__version__'):
                return line.split('=')[1].strip().strip('"').strip("'")
    return "1.1.0"


setup(
    name="StockDataMaster",
    version=read_version(),
    author="Arthur SU",
    author_email="arthur@lovefree.ai",
    description="专业的股票数据主数据接口系统",
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    url="https://github.com/weihong-su/StockDataMaster",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Financial and Insurance Industry",
        "Topic :: Office/Business :: Financial :: Investment",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
    python_requires=">=3.7",
    install_requires=[
        "pandas>=1.3.5",
        "numpy>=1.21.0",
    ],
    extras_require={
        'full': [
            'mootdx>=0.8.4',
            'baostock==0.9.1',
            'tushare>=1.2.89',
        ],
        'dev': [
            'pytest>=6.0',
            'pytest-cov>=2.0',
        ],
    },
    include_package_data=True,
    package_data={
        'StockDataMaster': [
            'config.json',
            'config.example.json',
            'LICENSE',
            'NOTICE',
            'lib/README.md',
            'lib/.gitignore',
            'lib/install_libs.py',
        ],
    },
    entry_points={
        'console_scripts': [
            'stockdatamaster-install-libs=StockDataMaster.lib.install_libs:install_builtin_libs',
        ],
    },
    keywords="stock data finance quantitative trading",
    license="Business Source License 1.1",
    project_urls={
        "Documentation": "https://weihong-su.github.io/StockDataMaster/",
        "Source": "https://github.com/weihong-su/StockDataMaster",
        "Bug Reports": "https://github.com/weihong-su/StockDataMaster/issues",
        "Funding": "https://buymeacoffee.com/suweihongc",
    },
)
