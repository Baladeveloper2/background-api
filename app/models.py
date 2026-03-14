import uuid
import json
from sqlalchemy import Column, String, Enum, DateTime, ForeignKey, Date, Integer, Text, TypeDecorator
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from .database import Base
import enum

class JSONEncodedDict(TypeDecorator):
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return '{}'
        return json.dumps(value)

    def process_result_value(self, value, dialect):
        if not value:
            return {}
        return json.loads(value)


class UserRole(str, enum.Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    ADMIN = "ADMIN"
    MANAGER = "MANAGER"
    VERIFIER = "VERIFIER"
    QC = "QC"
    CUSTOMER = "CUSTOMER"
    CANDIDATE = "CANDIDATE"

class Status(str, enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"

class CaseStatus(str, enum.Enum):
    PENDING = "PENDING"
    VERIFICATION = "VERIFICATION"
    QC = "QC"
    COMPLETED = "COMPLETED"
    INSUFFICIENT = "INSUFFICIENT"

class CheckStatus(str, enum.Enum):
    GREEN = "GREEN"
    RED = "RED"
    AMBER = "AMBER"
    INTERIM = "INTERIM"
    STOP = "STOP"

class User(Base):
    __tablename__ = "users"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255))
    role = Column(Enum(UserRole), default=UserRole.VERIFIER)
    role_id = Column(String(36), ForeignKey("roles.id"), nullable=True) # New RBAC Role
    status = Column(Enum(Status), default=Status.ACTIVE)
    territory = Column(String(255), nullable=True)
    business_unit = Column(String(255), nullable=True)
    bvs_permissions = Column(JSONEncodedDict, default=lambda: {
        "bms": {"applicants": True, "customer": True, "batch": True},
        "bvs": {"verification": True, "qc": True, "data_entry": True},
        "candidate": {"management": True},
        "mis": {"report": True},
        "admin": {"panel": True}
    })
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    role_rel = relationship("Role", backref="users")

class Role(Base):
    __tablename__ = "roles"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), unique=True, nullable=False)
    description = Column(String(500), nullable=True)
    permissions = Column(JSONEncodedDict, default=lambda: {}) # e.g. {"bvs.verification": true}
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Module(Base):
    __tablename__ = "modules"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), unique=True, nullable=False)
    code = Column(String(100), unique=True, nullable=False) # e.g. "bvs.verification"
    category = Column(String(100), nullable=False) # e.g. "BVS"
    description = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())



class Customer(Base):
    __tablename__ = "customers"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    short_code = Column(String(50), nullable=True)
    contact_person = Column(String(255))
    email = Column(String(255), unique=True, index=True)
    phone = Column(String(20))
    address = Column(Text)
    report_format = Column(String(100), default="Report Format-1 (Normal)")
    customer_agreement = Column(String(255), nullable=True)
    package_enabled = Column(Integer, default=0) # SQLite/MySQL boolean compatible
    status = Column(Enum(Status), default=Status.ACTIVE)
    pricing_config = Column(JSONEncodedDict) # e.g. {"employment": 100, "education": 50}

class Candidate(Base):
    __tablename__ = "candidates"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    email = Column(String(255), index=True)
    phone = Column(String(20))
    dob = Column(Date)
    address_details = Column(JSONEncodedDict)
    documents = Column(JSONEncodedDict) # List of Cloudinary URLs/Metadata

class Batch(Base):
    __tablename__ = "batches"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    customer_id = Column(String(36), ForeignKey("customers.id"))
    batch_no = Column(String(50), unique=True, index=True)
    upload_date = Column(DateTime(timezone=True), server_default=func.now())
    file_url = Column(String(255))

class Case(Base):
    __tablename__ = "cases"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_ref_no = Column(String(50), unique=True, index=True)
    customer_id = Column(String(36), ForeignKey("customers.id"))
    candidate_id = Column(String(36), ForeignKey("candidates.id"))
    batch_id = Column(String(36), ForeignKey("batches.id"), nullable=True)
    status = Column(Enum(CaseStatus), default=CaseStatus.PENDING)
    received_date = Column(DateTime(timezone=True), server_default=func.now())
    completed_date = Column(DateTime(timezone=True), nullable=True)
    tat_days = Column(Integer, default=0)

class VerificationCheck(Base):
    __tablename__ = "verification_checks"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id = Column(String(36), ForeignKey("cases.id"))
    check_type = Column(String(100)) # Education, Employment, etc.
    status = Column(Enum(CheckStatus), default=CheckStatus.INTERIM)
    data = Column(JSONEncodedDict) # Verification details
    verifier_remarks = Column(Text)
    verified_date = Column(DateTime(timezone=True), nullable=True)

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"))
    action = Column(String(255))
    details = Column(Text)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
