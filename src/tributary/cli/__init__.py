"""Command line interface.

One module per kind of command, so finding `trib topics` does not mean scrolling
past everything else. Importing a module is what registers its commands, which
is why they are imported here for their side effect -- and why the order
matters: `trib --help` lists panels, and commands within them, in the order they
were registered. The fence stops the import sorter from alphabetising it.
"""

# isort: off
from tributary.cli import setup  # noqa: F401
from tributary.cli import scheduled  # noqa: F401
from tributary.cli import ingest  # noqa: F401
from tributary.cli import sorting  # noqa: F401
from tributary.cli import labels  # noqa: F401
from tributary.cli import reading  # noqa: F401
from tributary.cli import serving  # noqa: F401
# isort: on
from tributary.cli.common import app

__all__ = ["app"]
