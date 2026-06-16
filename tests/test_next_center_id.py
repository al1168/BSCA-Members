from db.members import next_center_id


def test_increments_from_highest_active():
    assert next_center_id({10050, 10051, 10052}, terminated_ids=set()) == 10053


def test_skips_id_ending_in_4():
    # base 10052 -> 10053 ends in 3 (ok)? no: 10052+1 = 10053. Use 10053 base.
    assert next_center_id({10053}, terminated_ids=set()) == 10055  # 10054 skipped


def test_skips_ids_already_taken_by_terminated_above_active():
    # Highest active is 10052; 10053 and 10055 belong to terminated members.
    all_ids = {10052, 10053, 10055}
    terminated = {10053, 10055}
    # 10053 taken -> 10054 ends in 4 -> 10055 taken -> 10056
    assert next_center_id(all_ids, terminated_ids=terminated) == 10056


def test_falls_back_to_overall_max_when_all_terminated():
    all_ids = {10060, 10061}
    assert next_center_id(all_ids, terminated_ids={10060, 10061}) == 10062


def test_empty_database_uses_start_default():
    assert next_center_id(set(), terminated_ids=set(), start=10000) == 10000


def test_base_plus_one_ending_in_four_jumps_to_five():
    # Highest active 10063 -> 10064 ends in 4 -> 10065
    assert next_center_id({10063}, terminated_ids=set()) == 10065


def test_ignores_non_5_digit_ids_for_base():
    # The real data mixes 5-digit member IDs with a separate 7-digit scheme
    # (2.4M range) plus outliers. Only the largest 5-digit active member should
    # drive the next id — here 25362 -> 25363, not 10202938 -> 10202939.
    all_ids = {25362, 919191, 2400600, 9999999, 10202938}
    assert next_center_id(all_ids, terminated_ids=set()) == 25363


def test_falls_back_to_start_when_only_non_5_digit_ids_exist():
    # No 5-digit ids at all -> start default, not the 7-digit max.
    assert next_center_id({2400600, 9999999}, terminated_ids=set(),
                          start=10000) == 10000
