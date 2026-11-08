from playwright.sync_api import sync_playwright

from explore import capture_dom


def _capture(site, path):
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context()
        page = ctx.new_page()
        page.goto(site.url + "/login")
        page.fill("input[name=username]", "admin")
        page.fill("input[name=password]", "test-only-password")
        page.click("input[type=submit]")
        page.wait_for_url("**/home")
        page.goto(site.url + path)
        m = capture_dom.capture(page)
        b.close()
    return m


def test_list_page(site):
    m = _capture(site, "/patients")
    s, d = m["screen"], m["dom"]
    assert s["source"] == "dom" and m["schema_version"] == 1
    assert s["heuristic"]["kind"] == "list"
    grid = next(t for t in d["tables"] if t["kind"] == "grid")
    assert grid["headers"] == ["Name", "DOB", "Phone"]
    assert grid["row_count"] == 10 and grid["link_columns"] == [0]
    pag = s["heuristic"]["pagination"]
    assert pag["next"] == {"role": "link", "name": "Next >>"} and pag["page_size"] == 10
    row_links = [l for l in d["links"] if l["in_table"]]
    assert row_links and row_links[0]["header"] == "Name"
    assert any(l["in_nav"] and l["text"] == "Patients" for l in d["links"])
    assert "Name" in m["aria"]


def test_detail_page(site):
    m = _capture(site, "/patients/3")
    assert m["screen"]["heuristic"]["kind"] == "detail"
    kv = next(t for t in m["dom"]["tables"] if t["kind"] == "key_value")
    assert ["Last Name", "Lee"] in kv["pairs"]


def test_form_page_labels_required_and_options(site):
    m = _capture(site, "/patients/3/edit")
    assert m["screen"]["heuristic"]["kind"] == "form"
    form = m["dom"]["forms"][0]
    labels = {f["label"]: f for f in form["fields"]}
    assert labels["Last Name"]["required"] is True
    assert labels["First Name"]["required"] is False
    assert labels["Last Name"]["locator"]["css"] == "input[name=\"lname\"]"
    assert form["method"] == "post" and form["buttons"][0]["text"] == "Save"

    m2 = _capture(site, "/appointments/new?patient_id=3")
    prov = next(f for f in m2["dom"]["forms"][0]["fields"] if f["label"] == "Provider")
    assert prov["options"] == ["Dr. Lee", "Dr. Patel", "Hyg. Kim"] and prov["role"] == "combobox"
    assert next(f for f in m2["dom"]["forms"][0]["fields"] if f["label"] == "Date")["required"] is True


def test_summary_is_compact(site):
    m = _capture(site, "/patients")
    text = capture_dom.summarize(m)
    assert "Table (10 rows)" in text and len(text) < 3000
