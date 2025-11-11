#!/usr/bin/env python3
"""
Test CSV Import
===============

Simple test to import CSV into database and verify.
"""

import sys
import csv
import re
from pathlib import Path

# Add system path
sys.path.insert(0, str(Path(__file__).parent))

from system.database import SessionLocal
from system.models import Contact

# ============================================================================
# Normalization Functions
# ============================================================================

def normalize_name(name: str) -> str:
    """
    Normalize name: capitalize first letter of each word.

    Examples:
        "jean" -> "Jean"
        "DUPONT" -> "Dupont"
        "marie-claire" -> "Marie-Claire"
        "jean paul" -> "Jean Paul"
    """
    if not name:
        return ""
    # Use title() which capitalizes first letter of each word
    return name.strip().title()


def normalize_phone(phone: str) -> tuple[str, list[str]]:
    """
    Normalize and validate phone number.

    Rules:
    - Must start with international prefix (33, 31, 32, etc.)
    - Remove spaces, dots, dashes, parentheses
    - Must contain only digits after normalization

    Returns:
        tuple: (normalized_phone, list_of_errors)

    Examples:
        "33 6 12 34 56 78" -> ("33612345678", [])
        "06 12 34 56 78" -> ("", ["Missing international prefix (33, 31, 32, etc.)"])
        "+33612345678" -> ("33612345678", [])
        "33-6-12-34-56-78" -> ("33612345678", [])
    """
    if not phone:
        return "", ["Phone number is empty"]

    errors = []

    # Remove all non-digit characters except leading +
    original = phone.strip()
    normalized = re.sub(r'[^\d+]', '', original)

    # Remove leading + if present
    if normalized.startswith('+'):
        normalized = normalized[1:]

    # Check if only digits remain
    if not normalized.isdigit():
        errors.append(f"Phone contains invalid characters: '{original}'")
        return "", errors

    # Check international prefix (must start with known country codes)
    # Common codes: 33 (FR), 31 (NL), 32 (BE), 34 (ES), 39 (IT), 41 (CH), 44 (UK), 49 (DE), 1 (US/CA)
    valid_prefixes = ['33', '31', '32', '34', '39', '41', '44', '49', '1']

    has_valid_prefix = False
    for prefix in valid_prefixes:
        if normalized.startswith(prefix):
            has_valid_prefix = True
            break

    if not has_valid_prefix:
        errors.append(f"Missing international prefix (must start with: {', '.join(valid_prefixes)})")
        return "", errors

    # Check minimum length (international prefix + at least 8 digits)
    if len(normalized) < 10:
        errors.append(f"Phone number too short: '{normalized}' (minimum 10 digits)")
        return "", errors

    return normalized, errors


print("=" * 80)
print("TEST: CSV Import to Database")
print("=" * 80)

# ============================================================================
# Import CSV
# ============================================================================
print("\n[1] Importing CSV...")

csv_file = Path(__file__).parent / "test_contacts.csv"
if not csv_file.exists():
    print(f"❌ CSV file not found: {csv_file}")
    sys.exit(1)

db = SessionLocal()
imported_count = 0
skipped_count = 0
error_count = 0

try:
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        for row_num, row in enumerate(reader, start=2):  # start=2 because line 1 is header
            # ========== NORMALIZE PHONE ==========
            phone_raw = row.get('phone', '').strip()
            if not phone_raw:
                print(f"  ❌ Row {row_num}: Empty phone number - Skipping")
                error_count += 1
                continue

            phone, phone_errors = normalize_phone(phone_raw)
            if phone_errors:
                print(f"  ❌ Row {row_num}: Phone '{phone_raw}' - {', '.join(phone_errors)}")
                error_count += 1
                continue

            # ========== CHECK DUPLICATE ==========
            existing = db.query(Contact).filter(Contact.phone == phone).first()
            if existing:
                print(f"  ⚠️  Row {row_num}: Contact exists: {phone} - Skipping")
                skipped_count += 1
                continue

            # ========== NORMALIZE NAMES ==========
            first_name = normalize_name(row.get('first_name', ''))
            last_name = normalize_name(row.get('last_name', ''))
            email = row.get('email', '').strip().lower()  # Email always lowercase
            company = normalize_name(row.get('company', ''))

            # ========== CREATE CONTACT ==========
            contact = Contact(
                phone=phone,
                first_name=first_name,
                last_name=last_name,
                email=email,
                company=company
            )
            db.add(contact)
            imported_count += 1
            print(f"  ✅ Row {row_num}: Imported: {phone} - {first_name} {last_name}")

    db.commit()
    print(f"\n✅ Import completed!")
    print(f"   - Imported: {imported_count} contacts")
    print(f"   - Skipped: {skipped_count} contacts (already exist)")
    print(f"   - Errors: {error_count} contacts (validation failed)")

except Exception as e:
    print(f"\n❌ Import error: {e}")
    import traceback
    traceback.print_exc()
    db.rollback()
    sys.exit(1)

# ============================================================================
# Verify import
# ============================================================================
print("\n[2] Verifying import in database...")

try:
    total_contacts = db.query(Contact).count()
    recent_contacts = db.query(Contact).order_by(Contact.created_at.desc()).limit(10).all()

    print(f"\n📊 Database statistics:")
    print(f"   - Total contacts: {total_contacts}")

    print(f"\n📋 Last 10 imported contacts:")
    for i, contact in enumerate(recent_contacts, 1):
        created = contact.created_at.strftime('%Y-%m-%d %H:%M:%S')
        print(f"   {i}. {contact.phone}: {contact.first_name} {contact.last_name}")
        print(f"      Email: {contact.email}")
        print(f"      Created: {created}")

    # Test query by phone
    print(f"\n🔍 Testing query by phone (0612345001)...")
    test_contact = db.query(Contact).filter(Contact.phone == "0612345001").first()
    if test_contact:
        print(f"   ✅ Found: {test_contact.first_name} {test_contact.last_name}")
    else:
        print(f"   ❌ Not found")

    print("\n✅ Verification completed!")

except Exception as e:
    print(f"\n❌ Verification error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
finally:
    db.close()

print("\n" + "=" * 80)
print("TEST COMPLETED SUCCESSFULLY")
print("=" * 80)
