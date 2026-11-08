from explore.urlpattern import entity_guess, type_key, url_pattern


def test_ids_become_placeholders():
    assert url_pattern("http://x/patients/42") == "/patients/{id}"
    assert url_pattern("http://x/patients/42/edit") == "/patients/{id}/edit"
    assert url_pattern("http://x/orders/ORD1234") == "/orders/{id}"


def test_query_values():
    assert url_pattern("http://x/patients?page=2&q=smith") == "/patients?page={page}&q={q}"
    assert url_pattern("http://x/appointments/new?patient_id=7") == "/appointments/new?patient_id={patient_id}"
    # routing words are kept: they pick the page
    assert url_pattern("http://x/index.php?action=edit&id=5") == "/index.php?action=edit&id={id}"


def test_type_key_ignores_paging_and_search():
    assert type_key("http://x/patients") == type_key("http://x/patients?page=3&q=lee") == "/patients"
    assert type_key("http://x/index.php?action=list") != type_key("http://x/index.php?action=edit&id=1")


def test_entity_guess():
    assert entity_guess("http://x/patients/42/edit") == "Patient"
    assert entity_guess("http://x/appointments/new") == "Appointment"
    assert entity_guess("http://x/companies.php") == "Company"
    assert entity_guess("http://x/") is None


def test_slug_with_id_segments():
    a = "http://x/catalogue/category/books/travel_2/index.html"
    b = "http://x/catalogue/category/books/mystery_3/index.html"
    assert type_key(a) == type_key(b) == "/catalogue/category/books/{id}/index.html"
    assert url_pattern("http://x/catalogue/a-light-in-the-attic_1000/index.html") == "/catalogue/{id}/index.html"
    assert url_pattern("http://x/help.html") == "/help.html"
