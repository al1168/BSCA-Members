"""Transportation-authorization SQL shape + AuthEdge link constants.

Transport auths live in a separate [TransportAuthorization] table (a structural
twin of [Authorization]); the care<->transport relationship is stored in the
[AuthEdge] junction table. The select column list must be a prefix of
AUTHORIZATION_SELECT's (which adds the care-only [Plan Type]) so the shared
_map_auth_row mapper applies unchanged.
"""


def test_insert_transport_auth_targets_table_and_columns():
    from db.members import INSERT_TRANSPORT_AUTH
    assert "INSERT INTO [TransportAuthorization]" in INSERT_TRANSPORT_AUTH
    for col in ("[Center ID]", "[auth_start]", "[auth_end]", "[auth_days]",
                "[Health Plan]", "[created_at]", "[Member ID]", "[auth_number]"):
        assert col in INSERT_TRANSPORT_AUTH
    assert INSERT_TRANSPORT_AUTH.count("?") == 10


def test_update_transport_auth_targets_correct_columns():
    from db.members import UPDATE_TRANSPORT_AUTH
    assert "UPDATE [TransportAuthorization]" in UPDATE_TRANSPORT_AUTH
    for col in ("[auth_start]=?", "[auth_end]=?", "[auth_days]=?",
                "[Health Plan]=?", "[Member ID]=?", "[auth_number]=?",
                "[effective_start]=NULL", "[effective_end]=NULL"):
        assert col in UPDATE_TRANSPORT_AUTH
    assert "WHERE [ID]=?" in UPDATE_TRANSPORT_AUTH


def test_delete_transport_auth_targets_table():
    from db.members import DELETE_TRANSPORT_AUTH
    assert DELETE_TRANSPORT_AUTH == "DELETE FROM [TransportAuthorization] WHERE [ID]=?"


def test_transport_select_columns_match_authorization_select():
    # The transport column list is a prefix of the authorization one (which adds
    # the care-only [Plan Type] at the end), so the shared _map_auth_row keeps
    # working by index; only the FROM table differs otherwise.
    from db.members import TRANSPORT_AUTH_SELECT, AUTHORIZATION_SELECT
    assert "FROM [TransportAuthorization]" in TRANSPORT_AUTH_SELECT
    assert "WHERE [Center ID]=?" in TRANSPORT_AUTH_SELECT
    cols_t = TRANSPORT_AUTH_SELECT.split("FROM")[0].strip()
    cols_a = AUTHORIZATION_SELECT.split("FROM")[0].strip()
    assert cols_a == cols_t + ",[Plan Type]"


def test_insert_auth_edge_targets_join_table():
    from db.members import INSERT_AUTH_EDGE
    assert "INSERT INTO [AuthEdge]" in INSERT_AUTH_EDGE
    assert "[authorization_id]" in INSERT_AUTH_EDGE
    assert "[transport_authorization_id]" in INSERT_AUTH_EDGE
    assert INSERT_AUTH_EDGE.count("?") == 2


def test_delete_auth_edge_by_transport():
    from db.members import DELETE_AUTH_EDGE_BY_TRANSPORT
    assert "DELETE FROM [AuthEdge]" in DELETE_AUTH_EDGE_BY_TRANSPORT
    assert "[transport_authorization_id]=?" in DELETE_AUTH_EDGE_BY_TRANSPORT


def test_auth_edge_select_columns():
    from db.members import AUTH_EDGE_SELECT
    assert "FROM [AuthEdge]" in AUTH_EDGE_SELECT
    for col in ("[ID]", "[authorization_id]", "[transport_authorization_id]"):
        assert col in AUTH_EDGE_SELECT
