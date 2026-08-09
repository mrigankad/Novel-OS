"""Single source of the API version.

Its own module because `api/__init__` imports `main`, so anything `main` and
`routes` both need has to live outside the package root to avoid a cycle. The
string was previously duplicated in both files, which is the sort of thing that
silently drifts and then makes `/health` lie about what is deployed.
"""

__version__ = "0.3.0"
