from forgegod.cli_ux import build_banner_text, build_mini_banner_text


def test_build_banner_text_matches_official_cli_mark():
    plain = build_banner_text("9.9.9").plain.splitlines()
    assert plain == [
        "                 .",
        "            .-==========-.",
        "         .-'   .-====-.   '-.",
        "              \\________/",
        "                 /\\",
        "                / /\\ \\",
        "               / /  \\ \\",
        "              / /(_1_)\\ \\",
        "             /_/_______\\_\\",
        "",
        "   F O R G E G O D  v9.9.9",
        "   Autonomous coding engine",
    ]


def test_build_mini_banner_text_is_compact_and_brand_consistent():
    assert build_mini_banner_text("9.9.9").plain == "( ) /1\\ ForgeGod v9.9.9"
