"""Every module says where its rules come from."""

import pytest

from pyktane.packs import Manual
from pyktane.vanilla import PACK
from pyktane.vanilla._manual import MANUAL_URL, MANUAL_VERSION

MODULES = sorted(Manual.load().modules.values(), key=repr)


@pytest.mark.parametrize("module", MODULES, ids=repr)
def test_every_module_links_its_manual_page(module: object) -> None:
    url = getattr(module, "manual_url", "")
    assert url.startswith("https://"), f"{module!r} needs a manual_url"


@pytest.mark.parametrize("module", PACK.modules, ids=repr)
def test_vanilla_links_the_official_manual(module: object) -> None:
    url: str = getattr(module, "manual_url")  # noqa: B009
    assert url.startswith(f"{MANUAL_URL}#")


def test_pack_version_is_the_manual_version() -> None:
    assert PACK.version == MANUAL_VERSION
