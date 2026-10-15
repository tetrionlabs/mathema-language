<!-- github-only -->
> This page is part of the mathema documentation, [read it on the site](https://mathema.tetrionlabs.com/language/reference/path/).
<!-- /github-only -->

# Paths

<!-- module: path_page -->

`L[path]` is every non-empty path text without a NUL character, the way
a program receives a path from a command line, a form or a config file.
Its hazards are the paths code that joins, opens or checks them most
often gets wrong, visited before any random path:

```python
from mathema_language.text.path_language import PATH

print([h.value for h in PATH.hazards()[:5]])
```

<!-- output -->
```text
['..', '../etc/passwd', 'a/../../b', 'a/../b', '/etc/passwd']
```

The rest are a doubled or trailing slash, a leading `./`, a name that
starts with a dash and is read as an option, a newline in a name, a
home-directory tilde that only a shell expands, a repository's own
`.git/config`, names outside ASCII, and a name longer than most
filesystems allow.

## Paths within a root

`L[path, within "/workspace"]` is the paths confined to a root: a
relative path with no `..` segment, or an absolute path that is the root
or lies under it, again with no `..` segment.

```python
from mathema_language.text.path_language import path_within

workspace = path_within("/workspace")
candidates = ["reports/q3.csv", "/workspace/out", "a/../b", "../etc/passwd", "/etc/passwd"]
print([p for p in candidates if workspace.contains(p)])
print(workspace.render(True))
```

<!-- output -->
```text
['reports/q3.csv', '/workspace/out']
L[path, within "/workspace"]
```

It is decided on the text, never by resolving it. `a/../b` stays inside
the root once resolved and is still outside the language, since a rule
that resolves `..` cannot be decided exactly by an SMT solver, and a
path that names what it means is the one to accept. The text is all it
reads: a symbolic link inside the root that points outside is not seen,
which is a job for whatever runs the program, not for a claim about its
arguments.

Both languages are defined by one regular expression, read in full,
which decides membership and is what mathema's z3 encoding translates,
so the two agree. Over a command line, an option whose choices all stay
inside the root is proven within it, and an option that takes any path
is falsified with the value the program would receive, such as `/`.

Until claims can spell `within` directly, build the language in code and
register it under a name of your own:

```python
import mathema.languages

mathema.languages.register_language("workspace_paths", workspace)
```
