import uuid
import json
from sqlalchemy import Column, String, Enum, DateTime, ForeignKey, Date, Integer, Text, TypeDecorator, Float
from sqlalchemy.dialects.mysql import MEDIUMTEXT
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base
from .enums import UserRole, Status, CaseStatus, CheckStatus
from datetime import datetime

class JSONEncodedDict(TypeDecorator):
    impl = MEDIUMTEXT
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return '{}'
        return json.dumps(value)

    def process_result_value(self, value, dialect):
        if not value:
            return {}
        return json.loads(value)

class JSONEncodedList(TypeDecorator):
    impl = MEDIUMTEXT
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return '[]'
        return json.dumps(value)

    def process_result_value(self, value, dialect):
        if not value:
            return []
        try:
            data = json.loads(value)
            return data if isinstance(data, list) else []
        except:
            return []

class User(Base):
    __tablename__ = "users"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255))
    role = Column(Enum(UserRole), default=UserRole.USER)
    role_id = Column(String(36), ForeignKey("roles.id"), nullable=True) # New RBAC Role
    status = Column(String(50), default=Status.ACTIVE)
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
    name = Column(String(255), index=True)
    city = Column(String(100), nullable=True)  # Replaces short_code
    contact_person = Column(String(255))
    phone = Column(String(50))
    email = Column(String(255))
    address = Column(Text)
    report_format = Column(String(50))
    customer_agreement = Column(String(255), nullable=True)
    active_status = Column(Integer, default=1)  # 0 for Off, 1 for On (Replaces package_enabled)
    status = Column(String(50), default="ACTIVE")
    created_at = Column(DateTime, default=datetime.utcnow)
    pricing_config = Column(JSONEncodedDict) # e.g. {"employment": 100, "education": 50}

class Partner(Base):
    __tablename__ = "partners"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False) # Organization
    executive_lead = Column(String(255))
    contact_points = Column(String(255)) # Email/Phone or JSON
    regional_cluster = Column(String(255))
    status = Column(String(50), default=Status.ACTIVE)
    cloud_status = Column(String(50), default="ACTIVE")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Candidate(Base):
    __tablename__ = "candidates"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    email = Column(String(255), index=True)
    phone = Column(String(20))
    dob = Column(Date)
    client_emp_code = Column(String(50), nullable=True)
    address_details = Column(JSONEncodedDict)
    gender = Column(String(20), nullable=True)
    address = Column(Text, nullable=True)
    documents = Column(JSONEncodedList) # List of Cloudinary URLs/Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())



class Batch(Base):
    __tablename__ = "batches"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    customer_id = Column(String(36), ForeignKey("customers.id"))
    batch_no = Column(String(50), unique=True, index=True)
    upload_date = Column(DateTime(timezone=True), server_default=func.now())
    file_url = Column(String(255))
    cases_count = Column(Integer, default=0)
    tat_days = Column(Integer, default=10)
    case_rate = Column(Float, default=0.0)

class Case(Base):
    __tablename__ = "cases"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_ref_no = Column(String(50), unique=True, index=True)
    customer_id = Column(String(36), ForeignKey("customers.id", ondelete="CASCADE"))
    candidate_id = Column(String(36), ForeignKey("candidates.id", ondelete="CASCADE"))
    batch_id = Column(String(36), ForeignKey("batches.id"), nullable=True)
    status = Column(String(50), default=CaseStatus.PENDING)
    received_date = Column(DateTime(timezone=True), server_default=func.now())
    completed_date = Column(DateTime(timezone=True), nullable=True)
    tat_days = Column(Integer, default=0)

    # Relationships
    candidate = relationship("Candidate", backref="cases")
    customer = relationship("Customer", backref="cases")
    batch = relationship("Batch", backref="cases")
    checks = relationship("VerificationCheck", backref="case")

class VerificationCheck(Base):
    __tablename__ = "verification_checks"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id = Column(String(36), ForeignKey("cases.id"))
    check_type = Column(String(100)) # Education, Employment, etc.
    status = Column(String(50), default=CheckStatus.INTERIM)
    data = Column(JSONEncodedDict) # Verification details
    digital_token = Column(String(100), unique=True, nullable=True) # For candidate link
    verifier_remarks = Column(Text)
    verified_date = Column(DateTime(timezone=True), nullable=True)

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"))
    action = Column(String(255))
    details = Column(Text)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
