from services import email_service


def test_send_email_records_in_test_mode(client, session):
    email_service.clear_sent_emails()

    email_service.send_email(
        to="alice@example.com",
        subject="Test Subject",
        body="Test body",
    )

    emails = email_service.get_sent_emails()
    assert len(emails) == 1
    assert emails[0]["to"] == "alice@example.com"
    assert emails[0]["subject"] == "Test Subject"
    assert emails[0]["body"] == "Test body"

    email_service.clear_sent_emails()


def test_forgot_password_sends_email(client, session):
    from models import User
    from services.user_service import hash_password

    email_service.clear_sent_emails()

    obj = User(
        email="bob@example.com",
        password_hash=hash_password("password-123"),
        first_name="Bob",
        last_name="User",
        role="OPERATIONS_MANAGER",
        mfa_enabled=False,
    )
    session.add(obj)
    session.commit()

    resp = client.post("/auth/forgot-password", json={"email": "bob@example.com"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "message" in data

    emails = email_service.get_sent_emails()
    assert len(emails) == 1
    assert emails[0]["to"] == "bob@example.com"
    assert "Reset your password" in emails[0]["subject"]
    assert "password reset code" in emails[0]["body"]

    email_service.clear_sent_emails()


def test_forgot_password_unknown_email_sends_no_email(client, session):
    email_service.clear_sent_emails()

    resp = client.post("/auth/forgot-password", json={"email": "nobody@example.com"})
    assert resp.status_code == 200, resp.text

    emails = email_service.get_sent_emails()
    assert len(emails) == 0

    email_service.clear_sent_emails()


def test_mfa_setup_sends_email(client, session, admin_client, admin_user):
    email_service.clear_sent_emails()

    resp = admin_client.post("/auth/mfa/setup")
    assert resp.status_code == 200, resp.text
    data = resp.json()

    emails = email_service.get_sent_emails()
    assert len(emails) == 1
    assert emails[0]["to"] == "admin@example.com"
    assert "MFA setup code" in emails[0]["subject"]
    assert data["token"] in emails[0]["body"]

    email_service.clear_sent_emails()
