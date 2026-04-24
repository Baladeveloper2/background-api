import enum

class UserRole(str, enum.Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    ADMIN = "ADMIN"
    MANAGER = "MANAGER"
    VERIFIER = "VERIFIER"
    QC = "QC"
    QA = "QA"
    CUSTOMER = "CUSTOMER"
    CANDIDATE = "CANDIDATE"
    USER = "USER"  # Generic base role for RBAC-only users

class Status(str, enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"

class CaseStatus(str, enum.Enum):
    PENDING = "PENDING"
    VERIFICATION = "VERIFICATION"
    QC = "QC"
    QA_PENDING = "QA_PENDING"
    QC_PENDING = "QC_PENDING"
    COMPLETED = "COMPLETED"
    INSUFFICIENT = "INSUFFICIENT"

class CheckStatus(str, enum.Enum):
    GREEN = "GREEN"
    RED = "RED"
    AMBER = "AMBER"
    INTERIM = "INTERIM"
    VERIFICATION = "VERIFICATION"
    STOP = "STOP"
    QC_PENDING = "QC_PENDING"

class NotificationChannel(str, enum.Enum):
    SYSTEM = "SYSTEM"
    EMAIL = "EMAIL"
    SMS = "SMS"

class NotificationCategory(str, enum.Enum):
    CASE_ASSIGNED = "CASE_ASSIGNED"
    INSUFFICIENT_DOCS = "INSUFFICIENT_DOCS"
    CASE_COMPLETED = "CASE_COMPLETED"
    FORM_SUBMITTED = "FORM_SUBMITTED"
    EMAIL_TRIGGERED = "EMAIL_TRIGGERED"
    SYSTEM_ALERT = "SYSTEM_ALERT"
    QC_REPORT_READY = "QC_REPORT_READY"
    QA_REPORT_READY = "QA_REPORT_READY"
