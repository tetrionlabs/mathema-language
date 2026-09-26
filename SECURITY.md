# Security policy

Report a suspected vulnerability privately to security@tetrion.co rather
than opening a public issue. You'll get an acknowledgement within five
business days and a fix or a considered response within thirty.

This package evaluates nothing it is handed: it builds strings and
records from its own generators, tests membership with standard-library
parsers, and takes no network or subprocess action, so the realistic
surface is the code paths of those parsers on the hazard inputs the
package deliberately produces.
