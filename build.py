import os

from Cython.Build import cythonize
from setuptools import Distribution, Extension


cython_dir = os.path.join("src")
extensions = [
    Extension(
        "cwtch.core",
        [
            os.path.join(cython_dir, "core.pyx"),
        ],
    ),
    Extension(
        "cwtch.metadata",
        [
            os.path.join(cython_dir, "metadata.pyx"),
        ],
    ),
]

ext_modules = cythonize(
    extensions,
    include_path=[".", cython_dir],
)
dist = Distribution({"ext_modules": ext_modules})

dist.run_command("build_ext")
build_ext_cmd = dist.get_command_obj("build_ext")
build_ext_cmd.copy_extensions_to_source()
