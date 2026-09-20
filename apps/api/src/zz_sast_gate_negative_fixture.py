"""Throwaway fixture for the SAST gate's CI negative test (issue #140).

Temporary: lives only on the throwaway branch `tmp/sast-negative-proof-140`, which is
deleted again after the `sast` job has been observed failing on it. Never part of the
real PR (#167).
"""


def compute(expression):
    return eval(expression)
