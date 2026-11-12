"""Override for python-for-android's bundled setuptools recipe.

The stock recipe builds setuptools 51.3.3 with the host interpreter. Combined
with a modern host setuptools it crashes while byte-compiling
(`byte_compile() got an unexpected keyword argument 'dry_run'`). The app does not
need setuptools at runtime, so this recipe installs nothing and the build moves on.
"""

from pythonforandroid.recipe import Recipe


class SetuptoolsRecipe(Recipe):
    version = "0"
    url = None
    built_libraries = {}

    def build_arch(self, arch):  # nothing to build
        return

    def prebuild_arch(self, arch):
        return

    def postbuild_arch(self, arch):
        return


recipe = SetuptoolsRecipe()
