"""Verify i18n contact form keys are complete."""
import json


def test_i18n_files_exist():
    """Both i18n files should exist."""
    with open("i18n_en.json") as f:
        en = json.load(f)
    with open("i18n_es.json") as f:
        es = json.load(f)
    assert "en" in en
    assert "es" in es


def test_contact_form_keys_present():
    """All contact form keys should exist in both files."""
    with open("i18n_en.json") as f:
        en = json.load(f)
    with open("i18n_es.json") as f:
        es = json.load(f)

    en_keys = set(en["en"].keys())
    es_keys = set(es["es"].keys())

    contact_form_keys = [k for k in en_keys if "form." in k or "contact." in k]
    assert len(contact_form_keys) >= 10, "Should have contact form keys"

    missing_in_es = set(contact_form_keys) - es_keys
    extra_in_es = set(contact_form_keys) - en_keys

    assert not missing_in_es, f"Missing in ES: {sorted(missing_in_es)}"
    assert not extra_in_es, f"Extra in ES: {sorted(extra_in_es)}"


def test_all_keys_match():
    """Same keys should exist in both files."""
    with open("i18n_en.json") as f:
        en = json.load(f)
    with open("i18n_es.json") as f:
        es = json.load(f)

    en_keys = set(en["en"].keys())
    es_keys = set(es["es"].keys())

    missing_in_es = sorted(en_keys - es_keys)
    extra_in_es = sorted(es_keys - en_keys)

    print(f"EN count: {len(en_keys)}")
    print(f"ES count: {len(es_keys)}")
    print(f"Missing in ES: {missing_in_es}")
    print(f"Extra in ES: {extra_in_es}")

    assert not missing_in_es, f"Keys missing in ES: {missing_in_es}"
    assert not extra_in_es, f"Extra keys in ES: {extra_in_es}"


if __name__ == "__main__":
    test_i18n_files_exist()
    test_contact_form_keys_present()
    test_all_keys_match()
    print("All tests passed!")
