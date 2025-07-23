"""Main Module."""

from git_twig.cli.commands import main
from git_twig.completions import PowershellComplete  # noqa: F401 - required to enable powershell completions

if __name__ == "__main__":
    main()
