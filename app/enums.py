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
