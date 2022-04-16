import glob
import multiprocessing
import os
import shutil
import subprocess
import sys

import setuptools
import setuptools.command.build_ext


# To allow for setup.py install from build/ directory; Why -b doesn't work with
# the install subcommand boggles me. This is our hack.
make_dir = os.getcwd()
source_dir = os.path.abspath(os.path.dirname(__file__))
os.chdir(source_dir)


class MakeExtension(setuptools.Extension):
    def __init__(self, name, sourcedir=""):
        setuptools.Extension.__init__(self, name, sources=[])
        self.sourcedir = os.path.abspath(sourcedir)


class MakeBuild(setuptools.command.build_ext.build_ext):
    def run(self):
        num_cpus = multiprocessing.cpu_count()
        try:
            out = subprocess.check_output(["make", "-v", "-j" + str(num_cpus)])
        except OSError:
            raise RuntimeError("Make must be installed to build the following extensions: " +
                               ", ".join(e.name for e in self.extensions))

        for ext in self.extensions:
            self.build_extension(ext)

    def build_extension(self, ext):
        extname = os.path.basename(ext.name)
        extdirname = os.path.dirname(ext.name)

        env = os.environ.copy()
        if env.get("PYTHON", None) is not None:
            env["PYTHON"] = sys.executable  # Use the Python setup.py is invoked with

        # build in make dir (e.g. build/)
        subprocess.check_call(["make", "install"], env=env, cwd=make_dir)

        # look for all *.so
        shared_objs = glob.glob(os.path.join(extdirname, "*.so"))
        for shared_obj in shared_objs:
            dest = os.path.join(self.build_lib, extdirname, os.path.basename(shared_obj))
            print("copying {} -> {}".format(shared_obj, dest))
            shutil.copyfile(shared_obj, dest)

        pyi = os.path.join(extdirname, extname) + ".pyi"
        if os.path.exists(pyi):
            dest = os.path.join(self.build_lib, extdirname, os.path.basename(pyi))
            print("copying {} -> {}".format(pyi, dest))
            shutil.copyfile(pyi, dest)


# This code is not (yet) intended for release!
command_blacklist = ["register", "upload"]
for command in command_blacklist:
    if command in sys.argv:
        print("Command {} has been blacklisted (private repo), exiting...".format(command), file=sys.stderr)
        sys.exit(2)


with open("requirements.txt") as f:
    required_modules = list(map(str.strip, f.readlines()))


setuptools.setup(
    name="viz3",
    version="0.0.1",
    author="Dylan Gardner",
    author_email="dylan.gardner@utah.edu",
    description="Composable 3D visualization framework for visualizing system and "
                "sensor metrics stored across different databases.",
    ext_modules=[MakeExtension("viz3/core")],
    packages=setuptools.find_packages(),
    package_data={"viz3": ["py.typed", ".pyi", "**/.pyi", "static/*"]},
    cmdclass=dict(build_ext=MakeBuild),
    install_requires=required_modules,
    url="https://github.com/CHPC-UofU/viz3",
    zip_safe=False,
)
