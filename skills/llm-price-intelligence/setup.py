from pathlib import Path
from setuptools import setup
from setuptools.command.build_py import build_py


class BuildWithRegistry(build_py):
    def run(self):
        super().run()
        self.copy_file("sources.yaml", str(Path(self.build_lib) / "mandapi_price_intelligence" / "sources.yaml"))


setup(cmdclass={"build_py": BuildWithRegistry})
