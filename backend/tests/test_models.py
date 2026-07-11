from app.models import DocumentStatus, SubjectType


def test_document_status_values() -> None:
    assert {item.value for item in DocumentStatus} == {
        "pending",
        "processing",
        "ready",
        "failed",
    }


def test_subject_type_values() -> None:
    assert {item.value for item in SubjectType} == {
        "authenticated",
        "user",
        "role",
        "department",
    }
