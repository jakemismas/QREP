"""The confirmed read: the user's frame and counts in, squares out.

It replaces automatic grid detection (plan section 5.B): geometry.py
validates the confirmed frame and counts and derives the field, sample.py
warps the field and samples every square, and diagnosis.py names every
outcome that stops a read. One module per ticket, so this package re-exports
nothing; callers import each module directly.
"""
