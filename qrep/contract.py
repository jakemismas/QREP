"""Bridge v2 contract: the Python half of web/src/engine/contract.ts.

The web worker checks CONTRACT_VERSION at boot through
bridge.contract_version() and refuses to boot on a mismatch, so a cached
wheel never serves a page built for another contract. Any change to the
bridge's request or response shapes bumps the version here and in
contract.ts in the same commit; tests/test_bridge.py fails when the two
literals differ (plan section 4.2).

Like the bridge, this module must never import cv2, typer or click.
"""

CONTRACT_VERSION = 2
