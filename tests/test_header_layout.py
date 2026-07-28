"""Header geometry regression: the header band must stay compact, not
compete with the tabs for the window's vertical space (a vertically-expanding
spacer anywhere in the header layout makes Qt split the surplus with it)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

TEST_DB = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..", "..", "BSCA", "scripts", "test_dbs", "populate_real_members.accdb",
    )
)

pytestmark = pytest.mark.skipif(
    not os.path.exists(TEST_DB), reason="test DB not present")


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def test_header_stays_compact_in_tall_window(qapp):
    from db.members import get_all_members
    from gui.member_tabs import MemberTabsWidget
    cid = get_all_members(TEST_DB)[0]["center_id"]
    w = MemberTabsWidget(cid, TEST_DB, "", "", False)
    w.resize(1600, 1000)
    w.show()
    qapp.processEvents()
    # Tabs directly below the compact header (photo 80px + margins). If the
    # header expands, they land hundreds of pixels down.
    assert w._tabs.y() < 250
    # And the tabs get the bulk of the window height.
    assert w._tabs.height() > 600
    w.close()
