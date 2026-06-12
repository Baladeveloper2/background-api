from typing import List, Type
from .base import BaseParser
from .identity_parsers import AadhaarParser, PANParser, PassportParser, VoterIDParser, DrivingLicenseParser
from .document_parsers import (
    EducationParser, EmploymentParser, BankStatementParser, AddressBillParser, 
    SalarySlipParser, ExperienceLetterParser, ReferenceLetterParser, 
    MarksheetParser, DrugTestParser, PoliceVerificationParser, DefaultParser
)

def get_registered_parsers() -> List[Type[BaseParser]]:
    return [
        AadhaarParser,
        PANParser,
        PassportParser,
        VoterIDParser,
        DrivingLicenseParser,
        EducationParser,
        MarksheetParser,
        EmploymentParser,
        SalarySlipParser,
        ExperienceLetterParser,
        ReferenceLetterParser,
        BankStatementParser,
        AddressBillParser,
        DrugTestParser,
        PoliceVerificationParser
    ]

def get_default_parser() -> Type[BaseParser]:
    return DefaultParser
